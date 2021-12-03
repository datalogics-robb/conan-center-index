def ENV_LOC = [:]
def ARCH = [
    'aix-32-conan-center-index': 'ppc32',
    'aix-64-conan-center-index': 'ppc64',
    'linux-x86-conan-center-index': 'x86',
    'linux-x64-conan-center-index': 'x64',
    'linux-arm-conan-center-index': 'armv8',
    'mac-x64-conan-center-index': 'x64',
    'mac-arm-conan-center-index': 'armv8',
    'sparcsolaris-32-conan-center-index': 'sparc',
    'sparcsolaris-64-conan-center-index': 'sparcv9',
    'windows-x86-conan-center-index': 'x86',
    'windows-x64-conan-center-index': 'x64']
pipeline {
    parameters {
        choice(name: 'PLATFORM_FILTER',
               choices: ['all',
                         'aix-32-conan-center-index',
                         'aix-64-conan-center-index',
                         'linux-x86-conan-center-index',
                         'linux-x64-conan-center-index',
                         'linux-arm-conan-center-index',
                         'mac-x64-conan-center-index',
                         'mac-arm-conan-center-index',
                         'sparcsolaris-32-conan-center-index',
                         'sparcsolaris-64-conan-center-index',
                         'windows-x86-conan-center-index',
                         'windows-x64-conan-center-index'],
               description: 'Run on specific platform')
        booleanParam defaultValue: false, description: 'Completely clean the workspace before building, including the Conan cache', name: 'CLEAN_WORKSPACE'
        booleanParam name: 'UPLOAD_ALL_RECIPES', defaultValue: false,
            description: 'Upload all recipes, instead of only recipes that changed since the last merge'
    }
    options{
        buildDiscarder logRotator(artifactDaysToKeepStr: '4', artifactNumToKeepStr: '10', daysToKeepStr: '7', numToKeepStr: '10')
            disableConcurrentBuilds()
    }
    agent {
        node {
            label 'noarch-conan-center-index'
            customWorkspace "workspace/${JOB_NAME}_noarch/"
        }
    }
    environment {
        CONAN_USER_HOME = "${WORKSPACE}"
        CONAN_NON_INTERACTIVE = '1'
        CONAN_PRINT_RUN_COMMANDS = '1'
        // AIX workaround. Avoids an issue caused by the jenkins java process which sets
        // LIBPATH and causes errors downstream
        LIBPATH = "randomval"
        DL_CONAN_CENTER_INDEX = 'all'
    }
    stages {
        stage('Clean/reset Git checkout for release') {
            when {
                anyOf {
                    expression { params.CLEAN_WORKSPACE == 'true' }
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
        stage('Upload new or changed recipes') {
            when {
                not {
                    changeRequest()
                }
            }
            steps {
                script {
                    if (env.BRANCH_NAME =~ 'master*') {
                        remote = 'conan-center-dl'
                    } else {
                        remote = 'conan-center-dl-staging'
                    }
                    if (params.UPLOAD_ALL_RECIPES) {
                        range = '--all'
                    } else {
                        // assuming this is due to a merge, upload recipes
                        // modified since just before the last merge. This is an
                        // incremental update to recipes, and will be much faster
                        // than uploading all 1100+ recipes.
                        range = "--since-before-last-merge"
                    }
                    sh ". ${ENV_LOC['noarch']}/bin/activate; invoke upload-recipes --remote ${remote} ${range}"
                }
            }
        }
        stage('Per-platform') {
            when {
                // Turn off for now; testing verified that the structure works (common part then matrix part),
                // and the per-platform tasks aren't there yet.
                expression { false }
            }
            matrix {
                agent {
                    node {
                        label "${NODE}"
                        customWorkspace "workspace/${JOB_NAME}_${ARCH[NODE]}/"
                    }
                }
                when { anyOf {
                    expression { params.PLATFORM_FILTER == 'all' }
                    expression { params.PLATFORM_FILTER == env.NODE }
                } }
                axes {
                    axis {
                        name 'NODE'
                        values 'aix-32-conan-center-index',
                            'aix-64-conan-center-index',
                            'linux-x86-conan-center-index',
                            'linux-x64-conan-center-index',
                            'linux-arm-conan-center-index',
                            'mac-x64-conan-center-index',
                            'mac-arm-conan-center-index',
                            'sparcsolaris-32-conan-center-index',
                            'sparcsolaris-64-conan-center-index',
                            'windows-x86-conan-center-index',
                            'windows-x64-conan-center-index'
                    }
                }
                stages {
                    stage('Clean/reset Git checkout for release') {
                        when {
                            anyOf {
                                expression { params.CLEAN_WORKSPACE == 'true' }
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

void printPlatformNameInStep(String node) {
    script {
        stage("Building on ${node}") {
            echo "Building on node: ${node}"
        }
    }
}
