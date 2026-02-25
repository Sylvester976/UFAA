# apps/roles/models.py

import uuid
from django.db import models


class Permission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)

    permissions = models.ManyToManyField(
        Permission,
        related_name="roles",
        blank=True
    )

    def __str__(self):
        return self.name