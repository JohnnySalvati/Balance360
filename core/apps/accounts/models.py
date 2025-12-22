from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Usuario del sistema.
    No acoplamos datos financieros acá.
    """
    pass
