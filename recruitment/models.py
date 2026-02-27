from django.db import models


class Gender(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name        = 'Gender'
        verbose_name_plural = 'Genders'
        ordering            = ['name']

    def __str__(self):
        return self.name

class EthnicGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name        = 'Ethnic Group'
        verbose_name_plural = 'Ethnic Groups'
        ordering            = ['name']

    def __str__(self):
        return self.name