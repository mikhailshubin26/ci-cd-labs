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
                docker run --rm --volumes-from teamcity-agent -w %teamcity.build.checkoutDir% python:3.13-slim sh -c "pip install --no-cache-dir -q bandit && bandit -r app -lll -iii"
            """.trimIndent()
        }

        script {
            name = "Secrets scan (Gitleaks)"
            id = "gitleaksScan"
            scriptContent = """
                set -e
                docker run --rm --volumes-from teamcity-agent zricethezav/gitleaks:latest dir %teamcity.build.checkoutDir%/app --redact --exit-code 1 -v
            """.trimIndent()
        }

        script {
            name = "Unit tests (pytest)"
            id = "unitTests"
            scriptContent = """
                set -e
                docker run --rm --volumes-from teamcity-agent -w %teamcity.build.checkoutDir% python:3.13-slim sh -c "pip install --no-cache-dir -q -r requirements.txt pytest httpx teamcity-messages && pytest tests/unit --teamcity -v"
            """.trimIndent()
        }
 
        script {
            name = "Integration tests (pytest + PostgreSQL)"
            id = "integrationTests"
            scriptContent = """
                set -e
                trap 'docker rm -f it-db-%build.number% >/dev/null 2>&1 || true; docker network rm it-net-%build.number% >/dev/null 2>&1 || true' EXIT
                docker network create it-net-%build.number%
                docker run -d --name it-db-%build.number% --network it-net-%build.number% --network-alias db -e POSTGRES_DB=testdb -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test postgres:16-alpine
                timeout 60 sh -c 'until docker exec it-db-%build.number% pg_isready -U test -d testdb; do sleep 1; done'
                docker run --rm --network it-net-%build.number% --volumes-from teamcity-agent -w %teamcity.build.checkoutDir% -e POSTGRES_DB=testdb -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test python:3.13-slim sh -c "pip install --no-cache-dir -q -r requirements.txt pytest httpx teamcity-messages && pytest tests/integration --teamcity -v"
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
