import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildSteps.dockerCommand
import jetbrains.buildServer.configs.kotlin.buildSteps.script
import jetbrains.buildServer.configs.kotlin.buildFeatures.dockerSupport
import jetbrains.buildServer.configs.kotlin.buildFeatures.sshAgent
import jetbrains.buildServer.configs.kotlin.triggers.vcs

version = "2026.2"

project {
    buildType(DockerBuild)
}

object DockerBuild : BuildType({
    name = "Docker build"

    params {
        param("docker.image.name", "mikhailshubin26/ci-cd-labs-app")
        param("docker.image.tag", "%build.number%")
        param("stage.host", "10.0.2.4")
        param("stage.user", "mshubin")
    }

    vcs {
        root(DslContext.settingsRoot)
    }

    steps {
        script {
            name = "Security scan (Bandit)"
            id = "banditScan"
            scriptContent = """
                set -e
                pip install --no-cache-dir bandit
                bandit -r app -lll -iii
            """.trimIndent()
            dockerImage = "python:3.13-slim"
            dockerPull = true
        }

        script {
            name = "Secrets scan (Gitleaks)"
            id = "gitleaksScan"
            scriptContent = """
                set -e
                docker run --rm --volumes-from teamcity-agent zricethezav/gitleaks:latest dir %teamcity.build.checkoutDir% --redact --exit-code 1 -v
            """.trimIndent()
        }

        dockerCommand {
            name = "Build image"
            id = "dockerBuild"
            commandType = build {
                source = file {
                    path = "Dockerfile"
                }
                namesAndTags = "%docker.image.name%:%docker.image.tag%"
                commandArgs = "--pull"
            }
        }

        dockerCommand {
            name = "Push image"
            id = "dockerPush"
            conditions {
                matches("teamcity.build.branch", "(refs/heads/)?(dev|prod)")
            }

            commandType = push {
                namesAndTags = "%docker.image.name%:%docker.image.tag%"
            }
        }

        script {
            name = "Copy compose to STAGE"
            id = "copyComposeStage"
            conditions {
                matches("teamcity.build.branch", "(refs/heads/)?dev")
            }
            scriptContent = """
                set -e
                scp -o StrictHostKeyChecking=accept-new docker-compose.stage.yaml %stage.user%@%stage.host%:~/music_shop/docker-compose.stage.yaml
            """.trimIndent()
        }

        script {
            name = "Deploy to STAGE"
            id = "deployStage"
            conditions {
                matches("teamcity.build.branch", "(refs/heads/)?dev")
            }
            scriptContent = """
                set -e
                ssh -o StrictHostKeyChecking=accept-new %stage.user%@%stage.host% "cd ~/music_shop && APP_TAG=%docker.image.tag% docker compose -f docker-compose.stage.yaml pull && APP_TAG=%docker.image.tag% docker compose -f docker-compose.stage.yaml up -d --remove-orphans"
            """.trimIndent()
        }

        script {
            name = "Verify STAGE"
            id = "verifyStage"
            conditions {
                matches("teamcity.build.branch", "(refs/heads/)?dev")
            }
            scriptContent = """
                set -e
                ssh -o StrictHostKeyChecking=accept-new %stage.user%@%stage.host% 'for i in $(seq 1 30); do curl -fsS -o /dev/null http://localhost:8000/docs && echo "STAGE OK, tag %docker.image.tag%" && exit 0; sleep 2; done; echo "STAGE FAILED"; exit 1'
            """.trimIndent()
        }
    }

    features {
        dockerSupport {
            loginToRegistry = on {
                dockerRegistryId = "PROJECT_EXT_3"
            }
        }
        sshAgent {
            teamcitySshKey = "stage_deploy"
        }
    }

    triggers {
        vcs {
            branchFilter = "+:*"
        }
    }
})
