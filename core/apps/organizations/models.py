from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL

class Organization(models.Model):
    name = models.CharField(max_length=150)
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='organizations'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Membership(models.Model):
    ROLE_OWNER = 'OWNER'
    ROLE_ADMIN = 'ADMIN'
    ROLE_USER = 'USER'

    ROLE_CHOICES = [
        (ROLE_OWNER, 'Owner'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_USER, 'User'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    class Meta:
        unique_together = ('user', 'organization')

    def __str__(self):
        return f'{self.user} - {self.organization} ({self.role})'
