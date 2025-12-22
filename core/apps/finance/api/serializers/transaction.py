from rest_framework import serializers
from apps.finance.models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "date",
            "account",
            "entity",
            "category",
            "amount",
            "direction",
            "description",
        ]

    def validate(self, data):
        instance = Transaction(**data)
        instance.clean()  # valida cierres
        return data
