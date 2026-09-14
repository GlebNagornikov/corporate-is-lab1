from django.db import models

# Create your models here.

class Employee(models.Model):
    full_name = models.CharField(max_length=200)
    position = models.CharField(max_length=100)
    hired_at = models.DateField()

    def __str__(self):
        return self.full_name

