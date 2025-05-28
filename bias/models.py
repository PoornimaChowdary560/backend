from django.db import models

class UploadedDataset(models.Model):
    file = models.FileField(upload_to="uploads/datasets/")  # Store uploaded CSV files
    uploaded_at = models.DateTimeField(auto_now_add=True)  # Timestamp when uploaded
    processed = models.BooleanField(default=False)  # Track if analysis is done


class BiasAnalysisResult(models.Model):
    dataset = models.ForeignKey(UploadedDataset, on_delete=models.CASCADE)  # Link dataset
    sensitive_feature = models.CharField(max_length=100)  # E.g., "gender", "race"
    accuracy = models.FloatField()  # Model accuracy score
    demographic_parity_difference = models.FloatField()  # Bias Score
    analyzed_at = models.DateTimeField(auto_now_add=True)  # Timestamp

class BiasCorrectionSuggestion(models.Model):
    analysis = models.ForeignKey(BiasAnalysisResult, on_delete=models.CASCADE)
    suggestion_text = models.TextField()  # Suggest fixes
    applied = models.BooleanField(default=False)  # Whether the fix was applied
    category = models.CharField(
        max_length=50, 
        choices=[("data", "Data Fix"), ("model", "Model Fix"), ("feature", "Feature Fix")],
        default="model"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Suggestion {self.id} for Analysis {self.analysis.id}"
