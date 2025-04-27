from django.contrib import admin
from django.db import connection
from django.contrib import messages
from .models import BilliardAnalysis

@admin.register(BilliardAnalysis)
class BilliardAnalysisAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at')
    actions = ['reset_ids']
    
    def reset_ids(self, request, queryset):
        """The management operation of resetting the ID increment sequence"""
        if not request.user.is_superuser:
            messages.error(request, "Only superusers can perform this operation")
            return
            
        # delete all records in the BilliardAnalysis table
        BilliardAnalysis.objects.all().delete()
        
        # reset the ID sequence to 1
        db_engine = connection.vendor
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM analysis_app_billiardanalysis;")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='analysis_app_billiardanalysis';")
                
        messages.success(request, f"The ID sequence has been reset (database type: {db_engine})")
    
    reset_ids.short_description = "Reset all records and reset the ID sequence to 1"