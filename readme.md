# SIG's Shared CloudFormation Templates

This is SIG's collection of CloudFormation templates. The templates are
delivered as "packages" and are intended for use with the 
[Sceptre Package Manager](https://github.com/sigdba/sceptre_package_template_handler).

## Template Documentation
- [CodeBuildProject](templates/CodeBuildProject/readme.md)
- [EcsCluster](templates/EcsCluster/readme.md)
  - [NodeTypeChangeWithAutoScaling.md](templates/EcsCluster/doc/NodeTypeChangeWithAutoScaling.md)
  - [Examples](templates/EcsCluster/examples)
- EcsMemAutoTune
- [EcsMonitorService](templates/EcsMonitorService/readme.md)
- [EcsWebService](templates/EcsWebService/readme.md)
  - [SampleMemoryValues.org](templates/EcsWebService/doc/SampleMemoryValues.org)
- [Efs](templates/Efs/readme.md)
- GlobalLogRetentionRules
- [MultihostElb](templates/MultihostElb/readme.md)
- [Server](templates/Server/readme.md)
- [Vpc](templates/Vpc/readme.md)

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
