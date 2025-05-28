import traceback
import os
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import FileResponse, HttpResponseNotFound
from django.conf import settings
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from .models import UploadedDataset,BiasAnalysisResult,BiasCorrectionSuggestion
from .serializers import DatasetUploadSerializer,BiasAnalysisResultSerializer,BiasCorrectionSuggestionSerializer
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet
#from fairlearn.metrics import demographic_parity_difference
from fairlearn.metrics import equal_opportunity_difference


class DatasetUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        file_serializer = DatasetUploadSerializer(data=request.data)
        if file_serializer.is_valid():
            dataset = file_serializer.save()
            return Response({"message": "File uploaded successfully!","dataset_id":dataset.id}, status=status.HTTP_201_CREATED)
        return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BiasAnalysisView(APIView):
    def post(self, request, *args, **kwargs):
        dataset_id = request.data.get('dataset_id')
        sensitive_feature = request.data.get('sensitive_feature')

        try:
            dataset = UploadedDataset.objects.get(id=dataset_id)
            df = pd.read_csv(dataset.file.path)

            # Convert column names to lowercase to avoid case-sensitivity issues
            df.columns = df.columns.str.lower()

            # Check if target and predicted columns exist
            missing_columns = []
            if "target" not in df.columns:
                missing_columns.append("target")
            if "predicted" not in df.columns:
                missing_columns.append("predicted")

            if missing_columns:
                return Response({'message': f"Missing columns: {', '.join(missing_columns)}"}, status=400)

            # Check if the sensitive feature exists
            if sensitive_feature.lower() not in df.columns:
                return Response({'message': f"Sensitive feature '{sensitive_feature}' not found in dataset."}, status=400)
            # Convert string labels to numeric (0 and 1)
            label_mapping = {"not hired": 0, "hired": 1}
            df["target"] = df["target"].map(label_mapping)
            df["predicted"] = df["predicted"].map(label_mapping)

            if df["target"].isna().any() or df["predicted"].isna().any():
                return Response({'message': "Error: Invalid values in 'target' or 'predicted' column. Check data format."}, status=400)
            # Extract columns
            y_true = df['target']
            y_pred = df['predicted']
            sensitive_column = df[sensitive_feature.lower()]

            # ✅ Debugging: Print values
            print("y_true:", y_true.tolist())
            print("y_pred:", y_pred.tolist())
            print("sensitive_column:", sensitive_column.tolist())

            # Perform bias analysis
            bias_score = equal_opportunity_difference(y_true=y_true, y_pred=y_pred, sensitive_features=sensitive_column)

            accuracy = (y_true == y_pred).mean() * 100

            # Save results
            analysis = BiasAnalysisResult.objects.create(
                dataset=dataset,
                sensitive_feature=sensitive_feature,
                accuracy=accuracy,
                demographic_parity_difference=bias_score
            )
            
             # ✅ Set 'processed' to True
            dataset.processed = True
            dataset.save()  # 🔹 Save the update in the database


            return Response({
                'message': 'Analysis completed successfully!',
                'analysis_id': analysis.id,
                'accuracy': accuracy,
                'bias_score': bias_score
            })

        except Exception as e:
            # ✅ Capture full error traceback
            error_details = traceback.format_exc()
            print("Full Error Traceback:\n", error_details)
            return Response({'message': f"Error: {str(e)}"}, status=500)



class GetAnalysisResultsView(APIView):
    def get(self, request, analysis_id, *args, **kwargs):
        try:
            analysis = BiasAnalysisResult.objects.get(id=analysis_id)
            serializer = BiasAnalysisResultSerializer(analysis)
            return Response(serializer.data)
        except BiasAnalysisResult.DoesNotExist:
            return Response({'error': 'Analysis not found'}, status=404)

class BiasReportView(APIView):
    def get(self, request, analysis_id, *args, **kwargs):
        try:
            analysis = BiasAnalysisResult.objects.get(id=analysis_id)
            dataset = analysis.dataset  # Get associated dataset
            
            # Load dataset from file
            df = pd.read_csv(dataset.file.path)
            df.columns = df.columns.str.lower()  # Ensure lowercase column names

            # Ensure sensitive feature exists
            if analysis.sensitive_feature.lower() not in df.columns:
                return Response({"message": f"Sensitive feature '{analysis.sensitive_feature}' not found in dataset."}, status=400)

            # Extract gender column
            gender_column = df[analysis.sensitive_feature.lower()]
            
            # ✅ Count occurrences of "Male" and "Female" (modify based on actual values)
            male_count = (gender_column == "male").sum()
            female_count = (gender_column == "female").sum()
            total = male_count + female_count if (male_count + female_count) > 0 else 1  # Avoid division by zero

            # Convert counts to percentages
            male_percentage = round((male_count / total) * 100, 2)
            female_percentage = round((female_count / total) * 100, 2)
     
            # ✅ Calculate Bias Levels Dynamically
            bias_score = analysis.demographic_parity_difference  # Already in your API
            highly_biased = round(bias_score * 500)  # Scale values
            moderate_bias = round((1 - bias_score) * 300)
            low_bias = round((1 - bias_score) * 150)

            data = {
                "accuracy": analysis.accuracy,
                "bias_score": analysis.demographic_parity_difference,
                "male_percentage": male_percentage,
                "female_percentage": female_percentage,
                "heatmap_data": [  
                    {"name": "Highly Biased", "size": highly_biased},
                    {"name": "Moderate Bias", "size": moderate_bias},
                    {"name": "Low Bias", "size": low_bias}
                ]
            }
            
            return Response({"message": "Report data retrieved", "data": data})
        except BiasAnalysisResult.DoesNotExist:
            return Response({"message": "Analysis not found"}, status=404)

class SuggestinView(APIView):
    def get(self, request, analysis_id, *args, **kwargs):
        try:
            analysis = BiasAnalysisResult.objects.get(id=analysis_id)
            dataset = analysis.dataset  
            
            df = pd.read_csv(dataset.file.path)
            df.columns = df.columns.str.lower()  

            # Ensure sensitive feature exists
            if analysis.sensitive_feature.lower() not in df.columns:
                return Response({"message": f"Sensitive feature '{analysis.sensitive_feature}' not found in dataset."}, status=400)

            # Extract gender column
            gender_column = df[analysis.sensitive_feature.lower()]
            
            male_count = (gender_column == "male").sum()
            female_count = (gender_column == "female").sum()
            total = male_count + female_count if (male_count + female_count) > 0 else 1  

            male_percentage = round((male_count / total) * 100, 2)
            female_percentage = round((female_count / total) * 100, 2)

            bias_score = analysis.demographic_parity_difference

            data = {
                "accuracy": analysis.accuracy,
                "bias_score": bias_score,
                "male_percentage": male_percentage,
                "female_percentage": female_percentage
            }

            # ✅ Intelligent Suggestions Based on Bias Score
            suggestions = []

            if bias_score > 0.5:
                suggestions.append(BiasCorrectionSuggestion.objects.create(
                    analysis=analysis,
                    suggestion_text="Rebalance dataset: Increase data diversity.",
                    category="data"
                ))
                suggestions.append(BiasCorrectionSuggestion.objects.create(
                    analysis=analysis,
                    suggestion_text="Apply bias mitigation techniques in training.",
                    category="model"
                ))
            if male_percentage > 70 or female_percentage > 70:
                suggestions.append(BiasCorrectionSuggestion.objects.create(
                    analysis=analysis,
                    suggestion_text="Remove gender column from training data.",
                    category="feature"
                ))

            return Response({"message": "Report data retrieved", "data": data, "suggestions":BiasCorrectionSuggestionSerializer(suggestions, many=True).data })

        except BiasAnalysisResult.DoesNotExist:
            return Response({"message": "Analysis not found"}, status=404)

# ✅ Apply fixes and redirect to Download Report page
class ApplyFixesView(APIView):
    def post(self, request, analysis_id, *args, **kwargs):
        try:
            suggestions = BiasCorrectionSuggestion.objects.filter(analysis_id=analysis_id, applied=False)
            suggestions.update(applied=True)  # Mark fixes as applied
            return Response({"message": "Fixes applied successfully!"})
        except Exception as e:
            return Response({"error": str(e)}, status=400)

# ✅ Generate and Download PDF Report
class DownloadReportView(APIView):
    def get(self, request, analysis_id, *args, **kwargs):
        try:
            # Fetch analysis results
            analysis = BiasAnalysisResult.objects.get(id=analysis_id)
            suggestions = BiasCorrectionSuggestion.objects.filter(analysis_id=analysis_id, applied=True)

            # Ensure directory exists
            BASE_DIR = settings.BASE_DIR
            report_folder = os.path.join(BASE_DIR, "generated_reports")
            os.makedirs(report_folder, exist_ok=True)

            pdf_filename = f"bias_report_{analysis_id}.pdf"
            pdf_filepath = os.path.join(report_folder, pdf_filename)

            # Create PDF
            doc = SimpleDocTemplate(pdf_filepath, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()

            # Title
            title = Paragraph(f"<b>Bias Analysis Report (ID: {analysis_id})</b>", styles["Title"])
            elements.append(title)
            elements.append(Spacer(1, 0.2 * inch))

            # General Report Info
            report_info = [
                ["Accuracy:", f"{analysis.accuracy}%"],
                ["Bias Score:", f"{analysis.demographic_parity_difference}"]
            ]
            table = Table(report_info, colWidths=[150, 250])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.3 * inch))

            # Applied Fixes
            elements.append(Paragraph("<b>Applied Fixes:</b>", styles["Heading2"]))
            elements.append(Spacer(1, 0.2 * inch))

            if suggestions:
                fixes_data = [[f"- {suggestion.suggestion_text}"] for suggestion in suggestions]
                fixes_table = Table(fixes_data, colWidths=[400])
                fixes_table.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]))
                elements.append(fixes_table)
            else:
                elements.append(Paragraph("No fixes applied.", styles["Normal"]))

            doc.build(elements)

            # Check if file exists before returning it
            if not os.path.exists(pdf_filepath):
                return HttpResponseNotFound("The report could not be generated.")

            return FileResponse(open(pdf_filepath, "rb"), as_attachment=True, filename=pdf_filename)

        except BiasAnalysisResult.DoesNotExist:
            return HttpResponseNotFound("Analysis not found.")
        except Exception as e:
            return HttpResponseNotFound(f"Error generating report: {e}")