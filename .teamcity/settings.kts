import jetbrains.buildServer.configs.kotlin.*
import jetbrains.buildServer.configs.kotlin.buildSteps.dockerCommand
import jetbrains.buildServer.configs.kotlin.buildFeatures.dockerSupport
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
    }

    vcs {
        root(DslContext.settingsRoot)
    }

    steps {
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
                matches("teamcity.build.branch", "refs/heads/(dev|prod)")
            }
            commandType = push {
                namesAndTags = "%docker.image.name%:%docker.image.tag%"
            }
        }
    }

        features {
        dockerSupport {
            loginToRegistry = on {
                dockerRegistryId = "PROJECT_EXT_3"
            }
        }
    }

    triggers {
        vcs {
            branchFilter = "+:<default>\n+:refs/heads/*"
        }
    }
})
