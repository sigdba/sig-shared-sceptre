# SIG's Shared CloudFormation Templates

This is SIG's collection of CloudFormation templates. The templates are
delivered as "packages" and are intended for use with the 
[Sceptre Package Manager](https://github.com/sigdba/sceptre_package_template_handler).

## Template Documentation
- [CodeBuildProject](templates/CodeBuildProject/readme.md) - Creates a CodeBuild project, an optional ECR repository, and associated resources and permissions.
  - [Examples](templates/CodeBuildProject/examples)
- [EcsCluster](templates/EcsCluster/readme.md) - Creates an EC2-backed cluster in ECS with optional auto-scaling.
  - [NodeTypeChangeWithAutoScaling.md](templates/EcsCluster/doc/NodeTypeChangeWithAutoScaling.md)
  - [Examples](templates/EcsCluster/examples)
- [EcsMemAutoTune](templates/EcsMemAutoTune/readme.md) - Creates a Lambda function which runs on a specified schedule to analyze the memory used by ECS containers and tune their memory reservation to match real-world usage.
- [EcsMonitorService](templates/EcsMonitorService/readme.md) - Provides a metric for memory utilization of EC2-backed ECS containers.
- [EcsWebService](templates/EcsWebService/readme.md) - Creates an ECS service along with it's related load-balancer resources like listener rules and a target group.
  - [SampleMemoryValues.org](templates/EcsWebService/doc/SampleMemoryValues.org)
- [Efs](templates/Efs/readme.md) - Creates an EFS volume and associated resources.
- [GlobalLogRetentionRules](templates/GlobalLogRetentionRules/readme.md) - Creates an AWS Lambda function which runs on a schedule to set the retention of CloudWatch log groups.
  - [Examples](templates/GlobalLogRetentionRules/examples)
- [IamMfa](templates/IamMfa/readme.md)
- [MultihostElb](templates/MultihostElb/readme.md) - Creates an Elastic Load Balancer and associated resources.
- [Server](templates/Server/readme.md) - Creates an EC2 instance and associated resources.
- [Vpc](templates/Vpc/readme.md) - Creates a VPC, its subnets, and optional customer gateway (site-to-site VPN).

## Repository Setup

The easiest way to use these templates is with the [Sceptre Package
Manager](https://github.com/sigdba/sceptre_package_template_handler).

### Plugin Installation

In most cases you will want to add `sceptre-package-template-handler` to your
`requirements.txt` file then either refresh your development environment or
install with pip:

```
pip install -Ur requirements.txt
```

Alternatively you can install it directly:

```
pip install -U sceptre-package-template-handler
```

### Repository Configuration

The repository information is best kept as a variable in Sceptre's root
configuration file (`sceptre/config/config.yaml`):

``` yaml
sig_repo:
  name: sig-shared-sceptre
  base_url: https://github.com/sigdba/sig-shared-sceptre
```

### Stack Configuration

To use a packaged template, use the following in place of `template_path` in
your stack configuration file:

``` yaml
template:
  type: package
  name: EcsWebService
  release: 5
  repository: {{ sig_repo }}
```

Note that you can always find the latest release number on [the release page](https://github.com/sigdba/sig-shared-sceptre/releases).
