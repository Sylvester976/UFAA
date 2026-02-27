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

class County(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.IntegerField(unique=True)

    class Meta:
        verbose_name        = 'County'
        verbose_name_plural = 'Counties'
        ordering            = ['code']

    def __str__(self):
        return self.name


class Constituency(models.Model):
    name   = models.CharField(max_length=100)
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name='constituencies')

    class Meta:
        verbose_name        = 'Constituency'
        verbose_name_plural = 'Constituencies'
        ordering            = ['name']

    def __str__(self):
        return f'{self.name} — {self.county.name}'


class SubCounty(models.Model):
    name   = models.CharField(max_length=100)
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name='sub_counties')

    class Meta:
        verbose_name        = 'Sub County'
        verbose_name_plural = 'Sub Counties'
        ordering            = ['name']

    def __str__(self):
        return f'{self.name} — {self.county.name}'


class Ward(models.Model):
    name         = models.CharField(max_length=100)
    constituency = models.ForeignKey(Constituency, on_delete=models.CASCADE, related_name='wards')

    class Meta:
        verbose_name        = 'Ward'
        verbose_name_plural = 'Wards'
        ordering            = ['name']

    def __str__(self):
        return f'{self.name} — {self.constituency.name}'