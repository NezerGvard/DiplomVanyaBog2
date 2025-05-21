import uuid
from django.db import models
from django.contrib.auth.models import User

class Test(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='uploads/')
    name = models.CharField(max_length=255)
    file_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.file_name = self.file.name
        if not self.name:
            self.name = self.file_name
        super(Test, self).save(*args, **kwargs)


class UserFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    file = models.ForeignKey(Test, on_delete=models.CASCADE)