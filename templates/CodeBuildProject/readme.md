# CodeBuildProject

Creates a CodeBuild project, an optional ECR repository, and associated
resources and permissions.

Within the build run, the following environment variables are defined:

- `REVISION` - The value of the `DefaultRevision` parameter unless overridden at
  launch time.
- `AWS_ACCOUNT_ID` - The ID CodeBuild project's account.
- `IMAGE_REPO_NAME` - The name of the optional ECS repository.

You can also specify up to six additional environment variables by specifying
the `ExtraEnv*` parameters. These can be used either to provide fixed values or
as prompts to be defined at launch time.

## Parameters

- `ArtifactBucket` (String) - **required** - The name of an S3 bucket used for build resources. If your project
produces artifacts, they will be stored here.


- `BuildSpec` (String) - The relative path within the source repository for the project's build specification.
  - **Default:** `buildspec.yml`

- `CreatesDockerImage` (String) - Set this to `"true"` to create an ECR repository and related resources.
  - **Default:** `false`

- `DefaultRevision` (String) - Default value for the `REVISION` environment variable.
  - **Default:** `1.0-SNAPSHOT`

- `EnvComputeType` (String) - The type of compute environment. This determines the number of CPU cores
and memory the build environment uses. For a list of supported values, see
[AWS::CodeBuild::Project Environment - ComputeType](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codebuild-project-environment.html#cfn-codebuild-project-environment-computetype)

  - **Default:** `BUILD_GENERAL1_SMALL`

- `EnvImage` (String) - **required** - The image tag or image digest that identifies the Docker image to use for
this build project. Banner application builds will typically use the
current x86_64 Amazon Linux 2 image (ex.
`aws/codebuild/amazonlinux2-x86_64-standard:3.0`.) Amazon provides
[a set of standard images](https://docs.aws.amazon.com/codebuild/latest/userguide/build-env-ref-available.html).


- `EnvType` (String) - The type of environment the builds will occur in. For a list of supported
values, see [AWS::CodeBuild::Project Environment - Type](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codebuild-project-environment.html#cfn-codebuild-project-environment-type).

  - **Default:** `LINUX_CONTAINER`

- `ExtraEnvType1` (String) - The type of this environment variable. For a list of supported values, see
[AWS::CodeBuild::Project EnvironmentVariable - Type](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codebuild-project-environmentvariable.html#cfn-codebuild-project-environmentvariable-type).

  - **Default:** `PLAINTEXT`

- `ExtraEnvType2` (String) - The type of this environment variable. For a list of supported values, see
[AWS::CodeBuild::Project EnvironmentVariable - Type](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codebuild-project-environmentvariable.html#cfn-codebuild-project-environmentvariable-type).

  - **Default:** `PLAINTEXT`

- `ExtraEnvType3` (String) - The type of this environment variable. For a list of supported values, see
[AWS::CodeBuild::Project EnvironmentVariable - Type](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codebuild-project-environmentvariable.html#cfn-codebuild-project-environmentvariable-type).

  - **Default:** `PLAINTEXT`

- `ExtraEnvType4` (String) - The type of this environment variable. For a list of supported values, see
[AWS::CodeBuild::Project EnvironmentVariable - Type](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codebuild-project-environmentvariable.html#cfn-codebuild-project-environmentvariable-type).

  - **Default:** `PLAINTEXT`

- `ExtraEnvType5` (String) - The type of this environment variable. For a list of supported values, see
[AWS::CodeBuild::Project EnvironmentVariable - Type](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codebuild-project-environmentvariable.html#cfn-codebuild-project-environmentvariable-type).

  - **Default:** `PLAINTEXT`

- `ExtraEnvType6` (String) - The type of this environment variable. For a list of supported values, see
[AWS::CodeBuild::Project EnvironmentVariable - Type](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codebuild-project-environmentvariable.html#cfn-codebuild-project-environmentvariable-type).

  - **Default:** `PLAINTEXT`

- `ExtraEnvVal1` (String) - The default value of this environment variable.
  - **Default:** ``

- `ExtraEnvVal2` (String) - The default value of this environment variable.
  - **Default:** ``

- `ExtraEnvVal3` (String) - The default value of this environment variable.
  - **Default:** ``

- `ExtraEnvVal4` (String) - The default value of this environment variable.
  - **Default:** ``

- `ExtraEnvVal5` (String) - The default value of this environment variable.
  - **Default:** ``

- `ExtraEnvVal6` (String) - The default value of this environment variable.
  - **Default:** ``

- `ExtraEnvVar1` (String) - The name of an extra environment variable available during the build.
  - **Default:** `EXTRA_ARG_1`

- `ExtraEnvVar2` (String) - The name of an extra environment variable available during the build.
  - **Default:** `EXTRA_ARG_2`

- `ExtraEnvVar3` (String) - The name of an extra environment variable available during the build.
  - **Default:** `EXTRA_ARG_3`

- `ExtraEnvVar4` (String) - The name of an extra environment variable available during the build.
  - **Default:** `EXTRA_ARG_4`

- `ExtraEnvVar5` (String) - The name of an extra environment variable available during the build.
  - **Default:** `EXTRA_ARG_5`

- `ExtraEnvVar6` (String) - The name of an extra environment variable available during the build.
  - **Default:** `EXTRA_ARG_6`

- `ProjectName` (String) - **required** - The name of the CodeBuild project

- `RepoArn` (String) - The ARN of the CodeCommit repository CodeBuild will build from. Leave the
default value if you are not using CodeCommit.

  - **Default:** `arn:aws:codecommit:unused::UNUSED`

- `RepoUrl` (String) - **required** - The location of the source code. This will normally be the HTTPS (*not
HTTPS-GRC*) URL of the CodeCommit repository. If you are using something
other than CodeCommit, see [AWS::CodeBuild::Project Source - Location](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codebuild-project-source.html#cfn-codebuild-project-source-location).


- `SourceType` (String) - The type of repository that contains the source code to be built. For a
list of supported values, see [AWS::CodeBuild::Project Source - Type](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-codebuild-project-source.html#cfn-codebuild-project-source-type).

  - **Default:** `CODECOMMIT`

