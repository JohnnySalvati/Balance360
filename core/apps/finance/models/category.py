from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100)

    is_transfer_root = models.BooleanField(default=False)
    is_income = models.BooleanField()

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.PROTECT,
    )

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

    def __str__(self):
        return self.full_name()

    # ----------------------------
    # Jerarquía
    # ----------------------------

    def full_name(self):
        if self.parent:
            return f"{self.parent.full_name()} > {self.name}"
        return self.name

    def ancestors(self):
        """
        Devuelve la lista de ancestros desde el padre hasta la raíz.
        """
        node = self.parent
        ancestors = []
        while node:
            ancestors.append(node)
            node = node.parent
        return ancestors

    # ----------------------------
    # Dominio: Transferencias
    # ----------------------------

    @classmethod
    def get_transfer_root(cls):
        """
        Devuelve la categoría raíz de Transferencias.
        Debe existir UNA sola.
        """
        return cls.objects.get(
            is_system=True,
            name="Transferencias",
            parent__isnull=True,
        )

    def is_transfer(self) -> bool:
        """
        True si esta categoría o alguno de sus padres es Transferencias.
        """
        if self.is_transfer_root:
            return True

        return any(
            ancestor.is_transfer_root for ancestor in self.ancestors()
        )
