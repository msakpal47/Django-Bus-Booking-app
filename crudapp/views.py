from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.core.mail import EmailMessage
from django.db.models import Sum, F
from .models import BusRoute, Booking
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
import qrcode
import os
from datetime import timedelta
from django.templatetags.static import static


# --------------------------------------
# Initialize predefined routes if not exists
# --------------------------------------
def initialize_routes():
    routes_info = [
        {"name": "Antop Hill to Goregaon", "bus_type": "AC", "adult_fare": 35, "child_fare": 20, "total_seats": 40},
        {"name": "Kopar Khairane to Uran", "bus_type": "Non-AC", "adult_fare": 25, "child_fare": 15, "total_seats": 35},
        {"name": "Kharghar Station to Vely Ship Taoja", "bus_type": "AC", "adult_fare": 30, "child_fare": 15, "total_seats": 40},
        {"name": "Marol Maroshi to Worli", "bus_type": "Non-AC", "adult_fare": 35, "child_fare": 20, "total_seats": 35},
        {"name": "Dindoshi to Kurla", "bus_type": "AC", "adult_fare": 30, "child_fare": 15, "total_seats": 40},
        {"name": "Borivali to Panvel", "bus_type": "Non-AC", "adult_fare": 35, "child_fare": 20, "total_seats": 40},
    ]

    for route in routes_info:
        BusRoute.objects.get_or_create(
            name=route["name"],
            bus_type=route["bus_type"],
            defaults={
                "adult_fare": route["adult_fare"],
                "child_fare": route["child_fare"],
                "total_seats": route["total_seats"],
            }
        )


# --------------------------------------
# Home page
# --------------------------------------
def home(request):
    return render(request, 'crudapp/home.html')


# --------------------------------------
# Bus booking view
# --------------------------------------
def bus_booking(request):
    initialize_routes()  # ensure routes exist
    routes = BusRoute.objects.all()

    # Prepare dictionary of available seats per route
    available_seats_per_route = {}
    routes_with_seats = []

    for route in routes:
        booked_seats = Booking.objects.filter(route=route).aggregate(
            total=Sum(F('adults') + F('children'))
        )['total'] or 0
        available = route.total_seats - booked_seats
        available_seats_per_route[route.id] = available
        routes_with_seats.append({
            'id': route.id,
            'name': route.name,
            'bus_type': route.bus_type,
            'adult_fare': float(route.adult_fare),
            'child_fare': float(route.child_fare),
            'available_seats': available
        })

    booking = None

    if request.method == 'POST':
        name = request.POST.get('name')
        route_id = request.POST.get('route')
        adults = int(request.POST.get('adults', 0))
        children = int(request.POST.get('children', 0))
        email_to = request.POST.get('email_to')

        route = get_object_or_404(BusRoute, id=route_id)
        total_passengers = adults + children
        available = available_seats_per_route[route.id]

        if total_passengers > available:
            booking = {'error': f'Only {available} seats available for {route.name} ({route.bus_type})'}
        else:
            new_booking = Booking.objects.create(
                name=name,
                route=route,
                adults=adults,
                children=children,
                email=email_to
            )
            booking = {'object': new_booking, 'ticket_number': new_booking.ticket_number}

            # Send email with ticket PDF if email provided
            if email_to:
                try:
                    pdf_buffer = generate_ticket_pdf(new_booking)
                    email = EmailMessage(
                        subject=f"Your Bus Ticket #{new_booking.ticket_number}",
                        body=f"Hello {new_booking.name},\n\nPlease find attached your bus ticket.\nTotal Fare: ₹{new_booking.total_fare}",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[email_to]
                    )
                    email.attach(f"Ticket_{new_booking.ticket_number}.pdf", pdf_buffer.read(), "application/pdf")
                    email.send()
                except Exception as e:
                    print("Email sending failed:", e)

    return render(request, 'crudapp/bus_booking.html', {
        'routes': routes_with_seats,
        'booking': booking,
        'available_seats_per_route': available_seats_per_route
    })


# --------------------------------------
# PDF generation
# --------------------------------------
def generate_ticket_pdf(booking):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # -----------------------------
    # Header background
    # -----------------------------
    p.setFillColor(colors.HexColor("#0077b6"))
    p.rect(0, height - 160, width, 160, fill=1, stroke=0)

    # -----------------------------
    # Logo
    # -----------------------------
    logo_path = os.path.join('crudapp', 'static', 'images', 'best_logo.png')
    logo_width, logo_height = 180, 90
    if os.path.exists(logo_path):
        p.drawImage(logo_path, (width - logo_width) / 2, height - 150, width=logo_width, height=logo_height, preserveAspectRatio=True)

    # -----------------------------
    # Title
    # -----------------------------
    p.setFont("Helvetica-Bold", 26)
    p.setFillColor(colors.HexColor("#ffde59"))  # Yellow
    p.drawCentredString(width / 2, height - 200, "Best Bus Ticket Confirmation")

    # -----------------------------
    # Ticket box
    # -----------------------------
    box_x, box_y = 50, 220
    box_width, box_height = width - 100, height - 240 - 160
    p.setFillColor(colors.HexColor("#e6f7ff"))
    p.roundRect(box_x, box_y, box_width, box_height, 20, fill=1, stroke=0)

    # -----------------------------
    # Ticket Details
    # -----------------------------
    p.setFont("Helvetica-Bold", 12)
    labels = ["Ticket No", "Passenger Name", "Route", "Class", "Adults", "Children", "Total Fare"]
    values = [
        booking.ticket_number,
        booking.name,
        booking.route.name,
        booking.route.bus_type,
        str(booking.adults),
        str(booking.children),
        f"₹{booking.total_fare:.2f}"
    ]

    y_start = box_y + box_height - 50
    for i in range(len(labels)):
        y = y_start - i * 38
        p.setFillColor(colors.HexColor("#0077b6"))
        p.drawString(box_x + 30, y, labels[i])

        # Highlight passenger name and AC/Non-AC class
        if labels[i] == "Passenger Name":
            p.setFont("Helvetica-Bold", 14)
            p.setFillColor(colors.HexColor("#ff4500"))
            p.drawRightString(box_x + box_width - 30, y, values[i])
            p.setFont("Helvetica-Bold", 12)
        elif labels[i] == "Class":
            class_color = colors.HexColor("#00b159") if booking.route.bus_type == "AC" else colors.HexColor("#ff6347")
            p.setFillColor(class_color)
            p.drawRightString(box_x + box_width - 30, y, values[i])
            p.setFillColor(colors.HexColor("#023e8a"))
        else:
            p.setFillColor(colors.HexColor("#023e8a"))
            p.drawRightString(box_x + box_width - 30, y, values[i])

        # Dashed separator line
        if i < len(labels) - 1:
            p.setStrokeColor(colors.HexColor("#00b4d8"))
            p.setLineWidth(1)
            p.setDash(4, 4)
            p.line(box_x + 20, y - 8, box_x + box_width - 20, y - 8)
            p.setDash()  # reset dash

    # -----------------------------
    # Boarding Time Box (above QR)
    # -----------------------------
    boarding_time = booking.booked_at + timedelta(minutes=30)
    boarding_box_height = 30
    boarding_box_width = 220
    boarding_box_x = box_x + 30
    boarding_box_y = box_y + 80

    p.setFillColor(colors.HexColor("#ffde59"))  # Yellow highlight
    p.roundRect(boarding_box_x, boarding_box_y, boarding_box_width, boarding_box_height, 5, fill=1, stroke=0)

    p.setFont("Helvetica-Bold", 10)
    p.setFillColor(colors.HexColor("#0077b6"))  # Dark blue text
    p.drawCentredString(boarding_box_x + boarding_box_width / 2, boarding_box_y + 10,
                        f"Boarding Time: {boarding_time.strftime('%H:%M, %d-%b-%Y')}")

    # -----------------------------
    # QR Code
    # -----------------------------
    qr_data = f"Ticket:{booking.ticket_number}|Name:{booking.name}|Route:{booking.route.name}|Class:{booking.route.bus_type}|Seats:{booking.adults}A,{booking.children}C|Boarding:{boarding_time.strftime('%H:%M %d-%b-%Y')}"
    qr_img = qrcode.make(qr_data)
    qr_dir = os.path.join("crudapp", "static", "images")
    if not os.path.exists(qr_dir):
        os.makedirs(qr_dir)
    qr_path = os.path.join(qr_dir, f"qr_{booking.id}.png")
    qr_img.save(qr_path)
    qr_reader = ImageReader(qr_path)
    p.drawImage(qr_reader, box_x + box_width - 150, box_y + 30, width=120, height=120)

    # -----------------------------
    # Footer & Terms
    # -----------------------------
    footer_height = 120
    p.setFillColor(colors.HexColor("#00b4d8"))
    p.rect(0, box_y - 60, width, footer_height, fill=1, stroke=0)

    p.setFont("Helvetica-Oblique", 10)
    p.setFillColor(colors.white)
    p.drawCentredString(width / 2, box_y + 40, "Thank you for booking with MyBusPortal! Travel safely.")

    # Terms & Conditions in Yellow
    terms = [
        "1. Please carry a valid ID while boarding.",
        "2. Show this ticket to the conductor at the time of boarding.",
        "3. Booking is non-refundable unless canceled by MyBusPortal.",
        "4. MyBusPortal is not responsible for personal belongings.",
        "5. Follow bus staff instructions for a safe journey."
    ]
    p.setFont("Helvetica-Bold", 8)
    p.setFillColor(colors.HexColor("#ffde59"))  # Yellow terms
    text_y = box_y + 25
    for term in terms:
        p.drawString(box_x + 30, text_y, term)
        text_y -= 12

    # -----------------------------
    # Finish
    # -----------------------------
    p.showPage()
    p.save()
    buffer.seek(0)

    if os.path.exists(qr_path):
        os.remove(qr_path)

    return buffer






# Download PDF
# --------------------------------------
def download_ticket_pdf(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    pdf_buffer = generate_ticket_pdf(booking)
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Ticket_{booking.ticket_number}.pdf"'
    return response


# --------------------------------------
# Send ticket email
# --------------------------------------
def send_ticket_email(request):
    if request.method == "POST":
        ticket_id = request.POST.get("ticket_id")
        email_to = request.POST.get("email_to")
        booking = get_object_or_404(Booking, id=ticket_id)

        if email_to:
            pdf_buffer = generate_ticket_pdf(booking)
            email = EmailMessage(
                subject=f"Your Bus Ticket #{booking.ticket_number}",
                body=f"Hello {booking.name},\n\nPlease find attached your bus ticket.\nTotal Fare: ₹{booking.total_fare}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email_to]
            )
            email.attach(f"Ticket_{booking.ticket_number}.pdf", pdf_buffer.read(), "application/pdf")
            email.send()

        return redirect('bus_booking')


# --------------------------------------
# Booking report
# --------------------------------------
def booking_report(request):
    bookings = Booking.objects.all().order_by('-booked_at')
    return render(request, 'crudapp/booking_report.html', {"bookings": bookings})


# --------------------------------------
# Ticket preview
# --------------------------------------
def ticket_preview(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    qr_data = f"Ticket:{booking.ticket_number}|Name:{booking.name}|Route:{booking.route.name}|Seats:{booking.adults}A,{booking.children}C"
    qr_img = qrcode.make(qr_data)
    qr_path = f"crudapp/static/images/qr_{booking.id}.png"
    qr_img.save(qr_path)
    qr_url = static(f"images/qr_{booking.id}.png")
    return render(request, 'crudapp/ticket_template.html', {'booking': booking, 'qr_url': qr_url})
