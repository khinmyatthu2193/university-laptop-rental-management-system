from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import AuditLog, DamageReport, Laptop, LaptopAssignment, RepairLog


ACTIVE_ASSIGNMENT_STATUSES = ('Issued', 'Overdue')
ACTIVE_REPAIR_STATUSES = ('Pending', 'Repairing')
USABLE_RETURN_CONDITIONS = {'Excellent', 'Good'}


def active_assignment(laptop):
    return LaptopAssignment.objects.filter(
        laptop=laptop,
        assignment_status__in=ACTIVE_ASSIGNMENT_STATUSES,
        actual_return_date__isnull=True,
    ).order_by('-id').first()


def active_repairs(laptop):
    return RepairLog.objects.filter(
        laptop=laptop,
        repair_status__in=ACTIVE_REPAIR_STATUSES,
    ).order_by('-id')


def has_unresolved_damage(laptop):
    return laptop.status == 'Damage' or DamageReport.objects.filter(laptop=laptop).exists()


def _audit_status_change(staff, laptop, old_status, new_status, description):
    if not staff or old_status == new_status:
        return
    AuditLog.objects.create(
        staff=staff,
        action_type='Update',
        target_table='laptop',
        record_id=str(laptop.pk),
        old_value=f'SerialNumber: {laptop.SerialNumber}; Status: {old_status}',
        new_value=f'SerialNumber: {laptop.SerialNumber}; Status: {new_status}',
        description=description,
    )


def audit_category_change(staff, laptop, old_category, new_category):
    if not staff or old_category == new_category:
        return
    AuditLog.objects.create(
        staff=staff,
        action_type='Update',
        target_table='laptop',
        record_id=str(laptop.pk),
        old_value=f'SerialNumber: {laptop.SerialNumber}; Laptop Category: {old_category or "Unclassified"}',
        new_value=f'SerialNumber: {laptop.SerialNumber}; Laptop Category: {new_category or "Unclassified"}',
        description='Laptop category changed',
    )


def set_status(laptop, status, staff=None, description='Updated laptop inventory status'):
    """Apply a guarded status transition to a locked laptop instance."""
    assignment = active_assignment(laptop)
    repairs_exist = active_repairs(laptop).exists()
    damage_exists = has_unresolved_damage(laptop)

    if status == 'Available' and (assignment or repairs_exist or damage_exists):
        raise ValidationError(
            f'Laptop {laptop.SerialNumber} cannot become Available while it has '
            'an active assignment, unresolved repair, or unresolved damage.'
        )
    if status == 'In Repair' and assignment:
        status = 'Assigned'
    if status == 'Assigned' and not assignment:
        raise ValidationError(
            f'Laptop {laptop.SerialNumber} cannot be Assigned without an active assignment.'
        )

    old_status = laptop.status
    if old_status != status:
        laptop.status = status
        laptop.save(update_fields=['status'])
        _audit_status_change(staff, laptop, old_status, status, description)
    return laptop


def reconcile_status(laptop, staff=None, description='Reconciled laptop inventory status'):
    """Choose the only status supported by the laptop's current evidence."""
    assignment = active_assignment(laptop)
    if assignment:
        desired_status = 'Assigned'
    elif active_repairs(laptop).exists():
        desired_status = 'In Repair'
    elif has_unresolved_damage(laptop):
        desired_status = 'Damage'
    else:
        desired_status = 'Available'
    return set_status(laptop, desired_status, staff, description)


@transaction.atomic
def assign_laptop(*, person, laptop, issue_date, expected_return_date, academic_year, staff=None):
    laptop = Laptop.objects.select_for_update().get(pk=laptop.pk)
    if active_assignment(laptop):
        raise ValidationError(f'Laptop {laptop.SerialNumber} already has an active assignment.')
    if active_repairs(laptop).exists() or has_unresolved_damage(laptop):
        raise ValidationError(f'Laptop {laptop.SerialNumber} is blocked by repair or damage.')
    if laptop.status != 'Available':
        raise ValidationError(f'Laptop {laptop.SerialNumber} is not Available.')

    assignment = LaptopAssignment.objects.create(
        person=person,
        laptop=laptop,
        issue_date=issue_date,
        expected_return_date=expected_return_date,
        academic_year=academic_year,
        assignment_status='Issued',
    )
    set_status(laptop, 'Assigned', staff, 'Assigned laptop')
    return assignment


@transaction.atomic
def start_repair(*, laptop, staff=None):
    laptop = Laptop.objects.select_for_update().get(pk=laptop.pk)
    if active_repairs(laptop).exists():
        raise ValidationError(f'Laptop {laptop.SerialNumber} already has an active repair workflow.')
    if active_assignment(laptop):
        return laptop
    set_status(laptop, 'In Repair', staff, 'Started laptop repair')
    return laptop


@transaction.atomic
def complete_repair(*, repair_log, staff=None):
    repair_log = RepairLog.objects.select_for_update().select_related('laptop').get(pk=repair_log.pk)
    laptop = Laptop.objects.select_for_update().get(pk=repair_log.laptop_id)
    repair_log.repair_status = 'Completed'
    repair_log.save(update_fields=['repair_status'])

    assignment = active_assignment(laptop)
    if assignment:
        set_status(laptop, 'Assigned', staff, 'Completed repair; active assignment preserved')
    elif active_repairs(laptop).exists():
        set_status(laptop, 'In Repair', staff, 'Completed repair; another repair remains active')
    elif has_unresolved_damage(laptop):
        set_status(laptop, 'Damage', staff, 'Completed repair; unresolved damage remains')
    else:
        set_status(laptop, 'Available', staff, 'Completed repair and verified usable')
    return repair_log


@transaction.atomic
def complete_return(*, laptop, assignment, condition, staff=None):
    laptop = Laptop.objects.select_for_update().get(pk=laptop.pk)
    assignment = LaptopAssignment.objects.select_for_update().get(pk=assignment.pk)
    assignment.assignment_status = 'Returned'
    assignment.actual_return_date = timezone.now().date()
    assignment.save(update_fields=['assignment_status', 'actual_return_date'])

    unresolved_damage = has_unresolved_damage(laptop) or condition == 'Damaged'
    if condition in USABLE_RETURN_CONDITIONS and not active_repairs(laptop).exists() and not unresolved_damage:
        set_status(laptop, 'Available', staff, 'Completed laptop return')
    elif unresolved_damage:
        set_status(laptop, 'Damage', staff, 'Completed return with damaged condition')
    else:
        set_status(laptop, 'In Repair', staff, 'Completed return requiring repair')
    return laptop, assignment


def inventory_discrepancies():
    """Return a read-only report of status versus assignment/repair evidence."""
    discrepancies = []
    for laptop in Laptop.objects.order_by('SerialNumber'):
        assignment = active_assignment(laptop)
        repairs = list(active_repairs(laptop))
        damage = has_unresolved_damage(laptop)
        reasons = []

        if assignment and laptop.status != 'Assigned':
            reasons.append('active assignment requires Assigned status')
        if laptop.status == 'Assigned' and not assignment:
            reasons.append('Assigned status has no active assignment')
        if repairs and laptop.status not in {'In Repair', 'Assigned'}:
            reasons.append('active repair requires In Repair or Assigned status')
        if laptop.status == 'In Repair' and not repairs:
            reasons.append('In Repair status has no active repair workflow')
        if laptop.status == 'Available' and (assignment or repairs or damage):
            reasons.append('Available status has a blocking condition')

        if reasons:
            discrepancies.append({
                'laptop': laptop,
                'assignment': assignment,
                'active_repairs': repairs,
                'reasons': reasons,
            })
    return discrepancies
