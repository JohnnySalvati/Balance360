# apps/finance/models/account.py

from django.db import models

class Account(models.Model):
    CASH = "cash"
    BANK = "bank"
    WALLET = "wallet"

    TYPE_CHOICES = [
        (CASH, "Efectivo"),
        (BANK, "Cuenta bancaria"),
        (WALLET, "Billetera virtual"),
    ]

    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    currency = models.CharField(max_length=3, default="ARS")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.currency})"
