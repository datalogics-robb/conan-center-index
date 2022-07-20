def ENV_LOC = [:]
// Which nodes build tools. The linux-x64-tools-conan-center-index is an older machine
// that uses an earlier glibc, so the tools will run on every machine.
def BUILD_TOOLS=[
    'aix-conan-center-index': true,
    'linux-x64-rhws6-conan-center-index': true,
    'linux-x64-rhel7-conan-center-index': true,
    'linux-arm-conan-center-index': true,
    'mac-x64-conan-center-index': true,
    'mac-arm-conan-center-index': true,
    'sparcsolaris-conan-center-index': true,
    'windows-conan-center-index': true,
]
pipeline {
    parameters {
        choice(name: 'PLATFORM_FILTER',
               choices: ['all',
                         'linux-x64-rhws6-conan-center-index',
                         'linux-x64-rhel7-conan-center-index',
                         'linux-arm-conan-center-index',
                         'mac-x64-conan-center-index',
                         'mac-arm-conan-center-index',
                         'sparcsolaris-conan-center-index',
                         'windows-conan-center-index'],
               description: 'Run on specific platform')
        booleanParam defaultValue: false, description: 'Completely clean the workspace before building, including the Conan cache', name: 'CLEAN_WORKSPACE'
        booleanParam name: 'UPLOAD_ALL_RECIPES', defaultValue: false,
            description: 'Upload all recipes, instead of only recipes that changed since the last merge'
        booleanParam name: 'FORCE_TOOL_BUILD', defaultValue: false,
            description: 'Force build of all tools. By default, Conan will download the tool and test it if it\'s already built'
        booleanParam name: 'FORCE_TOOL_BUILD_WITH_REQUIREMENTS', defaultValue: false,
            description: 'Force build of all tools, and their requirements. By default, Conan will download the tool and test it if it\'s already built'
    }
    options{
        buildDiscarder logRotator(artifactDaysToKeepStr: '4', artifactNumToKeepStr: '10', daysToKeepStr: '7', numToKeepStr: '10')
            disableConcurrentBuilds()
    }
    agent {
        node {
            label 'noarch-conan-center-index'
            customWorkspace "workspace/${JOB_NAME.replaceAll('/','_')}_noarch/"
        }
    }
    environment {
        CONAN_USER_HOME = "${WORKSPACE}"
        CONAN_NON_INTERACTIVE = '1'
        CONAN_PRINT_RUN_COMMANDS = '1'
        // Disable FileTracker on Windows, which can give FTK1011 on long path names
        TRACKFILEACCESS = 'false'
        // Disable node reuse, which gives intermittent build errors on Windows
        MSBUILDDISABLENODEREUSE = '1'
        // AIX workaround. Avoids an issue caused by the jenkins java process which sets
        // LIBPATH and causes errors downstream
        LIBPATH = "randomval"
        DL_CONAN_CENTER_INDEX = 'all'
        TOX_TESTENV_PASSENV = 'CONAN_USER_HOME CONAN_NON_INTERACTIVE CONAN_PRINT_RUN_COMMANDS CONAN_LOGIN_USERNAME CONAN_PASSWORD TRACKFILEACCESS MSBUILDDISABLENODEREUSE'
    }
    stages {
        stage('Clean/reset Git checkout for release') {
            when {
                anyOf {
                    expression { params.CLEAN_WORKSPACE }
                }
            }
            steps {
                echo "Clean noarch"
                script {
                    // Ensure that the checkout is clean and any changes
                    // to .gitattributes and .gitignore have been taken
                    // into effect
                    if (isUnix()) {
                        sh """
                        git rm -q -r .
                        git reset --hard HEAD
                        git clean -fdx
                        """
                    } else {
                        // On Windows, 'git clean' can't handle long paths in .conan,
                        // so remove that first.
                        bat """
                        if exist ${WORKSPACE}\\.conan\\ rmdir/s/q ${WORKSPACE}\\.conan
                            git rm -q -r .
                            git reset --hard HEAD
                            git clean -fdx
                            """
                    }
                }
            }
        }
        stage('Set-Up Environment') {
            steps {
                printPlatformNameInStep('noarch')
                echo "Set-Up Environment noarch"
                script {
                    if (isUnix()) {
                        sh './mkenv.py --verbose'
                        ENV_LOC['noarch'] = sh (
                            script: './mkenv.py --env-name',
                            returnStdout: true
                        ).trim()
                    } else {
                        // Using the mkenv.py script like this assumes the Python Launcher is
                        // installed on the Windows host.
                        // https://docs.python.org/3/using/windows.html#launcher
                        bat '.\\mkenv.py --verbose'
                        ENV_LOC['noarch'] = bat (
                            // The @ prevents Windows from echoing the command itself into the stdout,
                            // which would corrupt the value of the returned data.
                            script: '@.\\mkenv.py --env-name',
                            returnStdout: true
                        ).trim()
                    }
                }
            }
        }
        stage('Set up Conan') {
            steps {
                sh """. ${ENV_LOC['noarch']}/bin/activate
                  invoke conan.login"""
            }
        }
        stage('flake8') {
            steps {
                catchError(message: 'flake8 had errors', stageResult: 'FAILURE') {
                    script {
                        sh """. ${ENV_LOC['noarch']}/bin/activate
                                    rm -f flake8.log
                                    flake8 --format=pylint --output=flake8.log --tee"""
                    }
                }
            }
            post {
                always {
                    recordIssues(enabledForFailure: true,
                                 tool: flake8(pattern: 'flake8.log'),
                                 qualityGates: [[threshold: 1, type: 'TOTAL', unstable: false]])
                }
            }
        }
        stage('Upload new or changed recipes') {
            when {
                not {
                    changeRequest()
                }
            }
            steps {
                script {
                    def remote
                    if (env.BRANCH_NAME =~ 'master*') {
                        remote = 'conan-center-dl'
                    } else {
                        remote = 'conan-center-dl-staging'
                    }
                    def range
                    if (params.UPLOAD_ALL_RECIPES) {
                        range = '--all'
                    } else {
                        // make sure conan-io is available and up-to-date
                        sh "git remote | grep conan-io || git remote add conan-io https://github.com/conan-io/conan-center-index.git"
                        sh "git fetch conan-io"
                        // assuming this is due to a merge, upload recipes
                        // modified since just before the last merge. This is an
                        // incremental update to recipes, and will be much faster
                        // than uploading all 1100+ recipes.
                        range = "--since-before-last-merge --since-merge-from-branch=conan-io/master"
                    }
                    sh ". ${ENV_LOC['noarch']}/bin/activate; invoke upload-recipes --remote ${remote} ${range}"
                }
            }
        }
        stage('Per-platform') {
            matrix {
                agent {
                    node {
                        label "${NODE}"
                        customWorkspace "workspace/${JOB_NAME.replaceAll('/','_')}/"
                    }
                }
                when { anyOf {
                    expression { params.PLATFORM_FILTER == 'all' }
                    expression { params.PLATFORM_FILTER == env.NODE }
                } }
                axes {
                    axis {
                        name 'NODE'
                        values 'linux-x64-rhws6-conan-center-index',
                            'linux-x64-rhel7-conan-center-index',
                            'linux-arm-conan-center-index',
                            'mac-x64-conan-center-index',
                            'mac-arm-conan-center-index',
                            'sparcsolaris-conan-center-index',
                            'windows-conan-center-index'
                    }
                }
                environment {
                    CONAN_USER_HOME = "${WORKSPACE}"
                    DL_CONAN_CENTER_INDEX = productionOrStaging()
                }
                stages {
                    stage('Clean/reset Git checkout for release') {
                        when {
                            anyOf {
                                expression { params.CLEAN_WORKSPACE }
                            }
                        }
                        steps {
                            echo "Clean ${NODE}"
                            script {
                                // Ensure that the checkout is clean and any changes
                                // to .gitattributes and .gitignore have been taken
                                // into effect
                                if (isUnix()) {
                                    sh """
                                        git rm -q -r .
                                        git reset --hard HEAD
                                        git clean -fdx
                                        """
                                } else {
                                    // On Windows, 'git clean' can't handle long paths in .conan,
                                    // so remove that first.
                                    bat """
                                        if exist ${WORKSPACE}\\.conan\\ rmdir/s/q ${WORKSPACE}\\.conan
                                        git rm -q -r .
                                        git reset --hard HEAD
                                        git clean -fdx
                                        """
                                }
                            }
                        }
                    }
                    stage('Set-Up Environment') {
                        steps {
                            printPlatformNameInStep(NODE)
                            echo "Set-Up Environment ${NODE}"
                            script {
                                if (isUnix()) {
                                    sh './mkenv.py --verbose'
                                    ENV_LOC[NODE] = sh (
                                        script: './mkenv.py --env-name',
                                        returnStdout: true
                                    ).trim()
                                } else {
                                    // Using the mkenv.py script like this assumes the Python Launcher is
                                    // installed on the Windows host.
                                    // https://docs.python.org/3/using/windows.html#launcher
                                    bat '.\\mkenv.py --verbose'
                                    ENV_LOC[NODE] = bat (
                                        // The @ prevents Windows from echoing the command itself into the stdout,
                                        // which would corrupt the value of the returned data.
                                        script: '@.\\mkenv.py --env-name',
                                        returnStdout: true
                                    ).trim()
                                }
                            }
                        }
                    }
                    stage('Print environment') {
                        steps {
                            script {
                                if (isUnix()) {
                                    sh "env"
                                } else {
                                    bat "set"
                                }
                            }
                        }
                    }
                    stage('Set up Conan') {
                        steps {
                            script {
                                if (isUnix()) {
                                    sh """. ${ENV_LOC[NODE]}/bin/activate
                                        invoke conan.login"""
                                } else {
                                    bat """CALL ${ENV_LOC[NODE]}\\Scripts\\activate
                                        invoke conan.login"""
                                }
                            }
                        }
                    }
                    stage('build tools') {
                        when {
                            allOf {
                                not {
                                    changeRequest()
                                }
                                expression { BUILD_TOOLS[NODE] }
                            }
                        }
                        steps {
                            script {
                                def remote
                                if (env.BRANCH_NAME =~ 'master*') {
                                    remote = 'conan-center-dl'
                                } else {
                                    remote = 'conan-center-dl-staging'
                                }
                                def short_node = NODE.replace('-conan-center-index', '')
                                def force_build
                                if (params.FORCE_TOOL_BUILD_WITH_REQUIREMENTS) {
                                    force_build = '--force-build with-requirements'
                                } else if (params.FORCE_TOOL_BUILD) {
                                    force_build = '--force-build'
                                } else {
                                    force_build = ''
                                }
                                def pytest_command = "pytest -k build_tool ${force_build} --upload-to ${remote} --junitxml=build-tools.xml --html=${short_node}-build-tools.html"
                                if (isUnix()) {
                                    catchError(message: 'pytest had errors', stageResult: 'FAILURE') {
                                        script {
                                            // on macOS, /usr/local/bin is not in the path by default, and the
                                            // Python binaries tox is looking for may be in there
                                            sh """. ${ENV_LOC[NODE]}/bin/activate
                                                (env PATH=\$PATH:/usr/local/bin ${pytest_command})"""
                                        }
                                    }
                                }
                                else {
                                    catchError(message: 'pytest had errors', stageResult: 'FAILURE') {
                                        script {
                                            bat """CALL ${ENV_LOC[NODE]}\\Scripts\\activate
                                                ${pytest_command}"""
                                        }
                                    }
                                }
                            }
                        }
                        post {
                            always {
                                catchError(message: 'testing had errors', stageResult: 'FAILURE') {
                                    xunit (
                                        reduceLog: false,
                                        tools: [
                                            JUnit(deleteOutputFiles: true,
                                                  failIfNotNew: true,
                                                  pattern: 'build-tools.xml',
                                                  skipNoTestFiles: true,
                                                  stopProcessingIfError: true)
                                        ])
                                    archiveArtifacts allowEmptyArchive: true, artifacts: '*-build-tools.html', followSymlinks: false
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    post {
        unsuccessful {
            script {
                if (env.CHANGE_ID == null) {  // i.e. not a pull request; those notify in GitHub
                    slackSend(channel: "#conan",
                              message: "Unsuccessful build: ${env.JOB_NAME} ${env.BUILD_NUMBER} (<${env.BUILD_URL}|Open>)",
                              color: "danger")
                }
            }
        }
        fixed {
            script {
                if (env.CHANGE_ID == null) {  // i.e. not a pull request; those notify in GitHub
                    slackSend(channel: "#conan",
                              message: "Build is now working: ${env.JOB_NAME} ${env.BUILD_NUMBER} (<${env.BUILD_URL}|Open>)",
                              color: "good")
                }
            }
        }
    }
}

void productionOrStaging() {
    if (env.CHANGE_ID == null) {
        if (env.BRANCH_NAME =~ 'master*') {
            return 'production'
        } else {
            return 'staging'
        }
    } else {
        if (env.CHANGE_BRANCH =~ 'master*') {
            return 'production'
        } else {
            return 'staging'
        }
    }
}

void printPlatformNameInStep(String node) {
    script {
        stage("Building on ${node}") {
            echo "Building on node: ${node}"
        }
    }
}
