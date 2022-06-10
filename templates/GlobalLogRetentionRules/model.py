from typing import List, Optional

from pydantic import Field

from util import BaseModel


class RuleModel(BaseModel):
    """A rule has a single matching function and an optional action. If a log
    group matches a rule without an action then it will not be modified and
    further processing of that group will stop.

    Available matching functions: `starts_with`, `contains`, `regex`

    Available actions: `retain_days`"""

    override_retention: bool = Field(
        False,
        description="""When `false` log groups which already have a retention
        set will not be modified. When `true` the previous setting will be
        overriden.""",
    )
    starts_with: Optional[str] = Field(
        description="Matches log groups whose names start with the given string."
    )
    contains: Optional[str] = Field(
        description="Matches log groups whose names contain the given string."
    )
    regex: Optional[str] = Field(
        description="Matches log groups whose name matches the given regular expression."
    )
    retain_days: Optional[int] = Field(
        description="Matching log groups will have their retention set to the given number of days."
    )


class UserDataModel(BaseModel):
    schedule: str = Field(
        "rate(1 day)",
        description="The schedule on which the rules will be evaluated.",
        notes=[
            "**See Also:** [Creating an Amazon EventBridge rule that runs on a schedule](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)"
        ],
    )
    rules: List[RuleModel] = Field(
        description="The set of rules to apply to log groups.",
        notes=[
            """Rules are applied in the order specified until a matching rule is
               applied at which point processing continues with the next log
               group."""
        ],
    )
