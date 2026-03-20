"""
Admin — Module Attendance, AMN Employee Hub.
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from attendance.models import Attendance, AttendanceReport, DeviceRegistration, Office


# ─────────────────────────────────────────────────────────────────────────────
# Office
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'latitude', 'longitude',
                    'allowed_radius_meters', 'late_after_hour', 'is_active')
    list_filter = ('country', 'is_active')
    search_fields = ('name', 'address')
    list_editable = ('is_active', 'allowed_radius_meters')
    fieldsets = (
        (None, {'fields': ('name', 'address', 'country', 'is_active')}),
        (_('Coordonnées GPS'), {'fields': ('latitude', 'longitude', 'allowed_radius_meters')}),
        (_('Horaires de pointage'), {
            'fields': ('check_in_start_hour', 'check_in_end_hour', 'late_after_hour'),
        }),
    )


# ─────────────────────────────────────────────────────────────────────────────
# DeviceRegistration
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(DeviceRegistration)
class DeviceRegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_fingerprint', 'device_name', 'is_trusted',
                    'first_seen', 'last_seen')
    list_filter = ('is_trusted',)
    search_fields = ('user__username', 'user__email', 'device_fingerprint', 'device_name')
    raw_id_fields = ('user',)
    readonly_fields = ('first_seen', 'last_seen')
    list_editable = ('is_trusted',)


# ─────────────────────────────────────────────────────────────────────────────
# Attendance
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'check_in_time', 'office', 'status',
                    'distance_meters', 'is_suspicious', 'failure_reason')
    list_filter = ('status', 'is_suspicious', 'date', 'office')
    search_fields = ('user__username', 'user__email', 'device_fingerprint', 'ip_address')
    raw_id_fields = ('user', 'office')
    readonly_fields = ('check_in_time', 'latitude', 'longitude', 'distance_meters',
                       'device_fingerprint', 'ip_address')
    date_hierarchy = 'date'
    ordering = ('-check_in_time',)
    fieldsets = (
        (None, {'fields': ('user', 'office', 'date', 'check_in_time', 'status')}),
        (_('Localisation GPS'), {'fields': ('latitude', 'longitude', 'distance_meters')}),
        (_('Anti-fraude'), {'fields': ('device_fingerprint', 'ip_address', 'is_suspicious',
                                       'failure_reason')}),
        (_('Notes admin'), {'fields': ('admin_note',)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'office')


# ─────────────────────────────────────────────────────────────────────────────
# AttendanceReport
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(AttendanceReport)
class AttendanceReportAdmin(admin.ModelAdmin):
    list_display = ('date', 'total_employees', 'present_count', 'late_count',
                    'absent_count', 'suspicious_count', 'generated_at')
    readonly_fields = ('date', 'total_employees', 'present_count', 'late_count',
                       'absent_count', 'suspicious_count', 'report_data', 'generated_at')
    date_hierarchy = 'date'
    ordering = ('-date',)
