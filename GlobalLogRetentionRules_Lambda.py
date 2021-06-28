import boto3
import re

REGION = '${AWS::Region}'

CWL = boto3.client('logs', region_name=REGION)


def get_log_groups():
    paginator = CWL.get_paginator('describe_log_groups')
    for page in paginator.paginate():
        for group in page['logGroups']:
            yield group


def get_rule_matcher(rule, check_override=True):
    if check_override and not rule.get('override_retention', False):
        matcher = get_rule_matcher(rule, check_override=False)
        return lambda group: False if 'retentionInDays' in group else matcher(group)

    if 'starts_with' in rule:
        return lambda group: group['logGroupName'].startswith(rule['starts_with'])
    if 'contains' in rule:
        return lambda group: rule['contains'] in group['logGroupName']
    if 'regex' in rule:
        matcher = re.compile(rule['regex'])
        return lambda group: matcher.search(group['logGroupName']) is not None
    return lambda group: True


def set_retain_days(log_group, retain_days):
    group_name = log_group['logGroupName']
    cur_val = log_group.get('retentionInDays', None)
    if cur_val == retain_days:
        print(group_name, 'already has retainDays=', cur_val, 'no change needed.')
    else:
        print('Changing', group_name, 'retainDays from', cur_val, 'to', retain_days)
        CWL.put_retention_policy(logGroupName=group_name, retentionInDays=retain_days)


def get_action(rule):
    if 'retain_days' in rule:
        return lambda group: set_retain_days(group, int(rule['retain_days']))
    return lambda group: print('Log group', group['logGroupName'], 'matched rule with no action')


def get_eval_rule_fn(rule):
    matcher = get_rule_matcher(rule)
    action = get_action(rule)

    def eval_rule(group):
        if matcher(group):
            action(group)
            return True
        return False

    return eval_rule


def lambda_handler(event, _):
    print('event:', event)

    rules = [get_eval_rule_fn(r) for r in event['rules']]
    for group in get_log_groups():
        matched = False
        for rule in rules:
            if rule(group):
                matched = True
                break
        if not matched:
            print('Log group', group['logGroupName'], 'did not match any rules or already has a retention set')
