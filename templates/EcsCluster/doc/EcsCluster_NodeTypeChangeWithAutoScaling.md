# EcsCluster - Changing Container Instance Types with AutoScaling

## Starting Configuration
For this example we'll assume the following configuration with a single ASG/CapacityProvider:

```yaml
---
template_path: shared/EcsCluster.py

parameters:
  EnvName: mycluster
  VpcId: vpc-1234
  Subnets:
    - subnet-1234
    - subnet-5678

sceptre_user_data:
  node_security_groups: []
  auto_scaling_enabled: yes
  force_default_cps: yes
  ssm_key_admins:
    - "arn:aws:iam::${AWS::AccountId}:root"
  ingress_cidrs:
    - "172.26.16.0/20"
  scaling_groups:
    - name: Old
      key_name: the-key
      node_type: t2.small
      max_size: 10
      desired_size: 0
```

In this configuration there is a single scaling group named `Old` of type `t2.small` and we wish to switch to an 
instance type of `t2.large`. Also note that `force_default_cps` is set to `yes`. This is **required** for this procedure
to work.

## Step 1 - Add a second ASG

Add a second scaling group to the configuration with the desired instance type. Also set `in_default_cps` to `no` on 
the old ASG:

```yaml
  scaling_groups:
    - name: Old
      key_name: the-key
      node_type: t2.small
      max_size: 10
      desired_size: 0
      in_default_cps: no
    - name: New
      key_name: the-key
      node_type: t2.large
      max_size: 10
      desired_size: 0
```

Update the stack with this configuration. In the AWS console, observe services migrating from the old ASG to the new. 
After all services are stable on the new ASG, proceed to the next step.

## Step 2 - Remove the old ASG

Once all services have migrated to the new ASG, you can remove the old ASG from the configuration and update the stack:

```yaml
  scaling_groups:
    - name: New
      key_name: the-key
      node_type: t2.large
      max_size: 10
      desired_size: 0
```