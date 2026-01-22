from apps.finance.models.classification_rule import ClassificationRule

class RuleRegistry:
    _rules = None

    @classmethod
    def get_active_rules(cls):
        if cls._rules is None:
            cls._rules = list(
                ClassificationRule.objects
                .filter(is_active=True)
                .order_by("-confidence", "-pattern__length")
            )
        return cls._rules

    @classmethod
    def invalidate(cls):
        cls._rules = None
