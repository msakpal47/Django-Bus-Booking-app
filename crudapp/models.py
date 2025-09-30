from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
import random

# Choices for Bus Type
BUS_TYPE_CHOICES = [
    ('AC', 'AC'),
    ('Non-AC', 'Non-AC')
]

class BusRoute(models.Model):
    name = models.CharField(max_length=100)
    total_seats = models.PositiveIntegerField()
    bus_type = models.CharField(max_length=10, choices=BUS_TYPE_CHOICES, default='Non-AC')
    adult_fare = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('10.00'), validators=[MinValueValidator(0)]
    )
    child_fare = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('5.00'), validators=[MinValueValidator(0)]
    )

    class Meta:
        unique_together = ('name', 'bus_type')  # Ensures no duplicate route with same type
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.bus_type})"

    def available_seats(self):
        """Returns the number of available seats for this route."""
        booked = sum(b.total_passengers() for b in Booking.objects.filter(route=self))
        return self.total_seats - booked


class Booking(models.Model):
    name = models.CharField(max_length=100, default="Anonymous")
    route = models.ForeignKey(BusRoute, on_delete=models.CASCADE)
    adults = models.PositiveIntegerField(default=0)
    children = models.PositiveIntegerField(default=0)
    email = models.EmailField(null=True, blank=True)
    booked_at = models.DateTimeField(auto_now_add=True)
    ticket_number = models.CharField(max_length=50, editable=False, unique=True)
    total_fare = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(0)]
    )

    class Meta:
        ordering = ['-booked_at']

    def total_passengers(self):
        return self.adults + self.children

    def calculate_total_fare(self):
        """Calculate total fare for the booking."""
        if self.route:
            return (self.adults * self.route.adult_fare) + (self.children * self.route.child_fare)
        return Decimal('0.00')

    def clean(self):
        """Validate seat availability."""
        if self.route and self.total_passengers() > self.route.available_seats():
            raise ValidationError(
                f"Only {self.route.available_seats()} seats available for {self.route.name} ({self.route.bus_type})."
            )

    @property
    def route_display(self):
        """Formatted route for templates."""
        return f"{self.route.name} ({self.route.bus_type})"

    def save(self, *args, **kwargs):
        """Override save to generate ticket number, calculate total fare, and validate seats."""
        if not self.ticket_number:
            now = timezone.now()
            self.ticket_number = f"T{now.strftime('%Y%m%d%H%M%S')}{self.route.id if self.route else 0}{random.randint(100,999)}"
        self.total_fare = self.calculate_total_fare()
        self.clean()  # Ensure seat availability
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.route.name} ({self.route.bus_type}) - {self.ticket_number} - ₹{self.total_fare}"
