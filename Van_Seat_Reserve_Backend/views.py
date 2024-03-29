from .models import CustomUser, VanDriver, VanReservation,  Locations
from .serializers import RegisterSerializer, VanDriverSerializer, VanReservationSerializer, VanDriverListSerializer, LocationsSerializer, ResponseDriverCarSerializer, VanReservationListSerializer
from rest_framework import generics, permissions, exceptions
from rest_framework.viewsets import ModelViewSet
from .permissions import IsAdmin, IsDriver, IsUser
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
import datetime
import qrcode
from rest_framework.views import APIView
from io import BytesIO
from rest_framework.response import Response
from rest_framework import status
from django.urls import reverse
from django.conf import settings
from django.http import FileResponse
from django.shortcuts import render, get_object_or_404


class RegisterView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = RegisterSerializer


class ListLocations(generics.ListCreateAPIView):
    queryset = Locations.objects.all()
    serializer_class = LocationsSerializer
    permission_classes = [IsAuthenticated]


class ListCreateDriveRouteView(ModelViewSet):
    queryset = VanDriver.objects.all()
    serializer_class = VanDriverListSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        if self.request.user.role == 'admin' or self.request.user.role == 'user':
            return VanDriver.objects.all()
        
        else:
            raise PermissionDenied('Driver can not access this page')    
    


class CreateReservationAndViewTicket(generics.ListCreateAPIView):
    queryset = VanReservation.objects.all()
    serializer_class = VanReservationSerializer
    permission_classes = (IsAuthenticated, IsUser)

    def perform_create(self, serializer):
        user = self.request.user
        van_id = self.request.data.get('van')
        number_of_seat = int(self.request.data.get(
            'number_of_seat'))
        van = VanDriver.objects.get(id=van_id)

        amount_to_pay = van.price_per_unit * number_of_seat

        if van.number_of_seat < number_of_seat:
            raise exceptions.ValidationError(
                'Number of seat should be less than or equal to van seat')
        serializer.save(user=user, amount_to_pay=amount_to_pay, van=van)

        # Subtract number_of_seat from car.number_of_seat and save the van object

        van.number_of_seat -= number_of_seat
        # check if van number_of_seat is 0 then make is_available to False
        if van.number_of_seat == 0:
            van.is_available = False

        van.save()


class UserReservation(generics.ListCreateAPIView):
    queryset = VanReservation.objects.all()
    serializer_class = VanReservationSerializer
    permission_classes = (IsAuthenticated, IsUser)

    def perform_create(self, serializer):
        user = self.request.user
        van = self.request.data.get('van')
        number_of_seat = self.request.data.get('number_of_seat')

        van = VanDriver.objects.get(id=van)

        amount_to_pay = van.price_per_unit * number_of_seat

        if van.number_of_seat < number_of_seat:
            raise exceptions.ValidationError(
                'Number of seat should be less than or equal to van seat')
        serializer.save(user=user, amount_to_pay=amount_to_pay, van=van)

    def get_queryset(self):
        user = self.request.user
        return VanReservation.objects.filter(user=user)


# ---- mockup -----

class QrCodeToTicketVerification(generics.RetrieveAPIView):
    # ...

    queryset = VanReservation.objects.all()
    serializer_class = VanReservationSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )

        # ngrok url
        ngrok_url = 'https://caee-2001-fb1-148-6aeb-7916-19d5-8b97-3c18.ngrok-free.app'

        verify_url = reverse('mark-reservation-as-successful',
                             kwargs={'number_of_ticket': instance.number_of_ticket})

        full_url = ngrok_url + verify_url
        qr.add_data(full_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        byte_arr = BytesIO()
        img.save(byte_arr, format='PNG')

        byte_arr.seek(0)

        return FileResponse(byte_arr, content_type='image/png')


# ---- mockup -----
class MarkReservationAsSuccessful(APIView):

    def get(self, request, number_of_ticket, format=None):
        reservation = VanReservation.objects.get(
            number_of_ticket=number_of_ticket)
        if reservation.is_confirmed:
            # return Response({'status': 'already confirmed'}, status=status.HTTP_400_BAD_REQUEST)
            return render(request, 'status.html', {'status': 'already confirmed'})
        else:
            reservation.is_confirmed = True
            reservation.save()
            return render(request, 'status.html', {'status': 'success'})

        # reservation.is_confirmed = True
        # reservation.save()
        # return Response({'status': 'success'}, status=status.HTTP_200_OK)


class ListDriverResponse(generics.ListAPIView):
    serializer_class = ResponseDriverCarSerializer
    permission_classes = (IsAuthenticated, IsDriver)

    def get_queryset(self):
        user = self.request.user
        return VanDriver.objects.filter(driver=user)


class RetrieveUpdateDestroyDriveRouteView(ModelViewSet):
    queryset = VanDriver.objects.all()
    serializer_class = VanDriverSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def perform_create(self, serializer):
        startRoute = self.request.data.get('startRoute')
        endRoute = self.request.data.get('endRoute')
        driver = self.request.data.get('driver')

        startRoute = get_object_or_404(Locations, name=startRoute)
        endRoute = get_object_or_404(Locations, name=endRoute)
        id_driver = get_object_or_404(CustomUser, username=driver)

        time = self.request.data.get('time')
        time = datetime.datetime.strptime(time, '%H:%M:%S').time()

        if startRoute == endRoute:
            raise exceptions.ValidationError(
                'Start and End Route should not be same')

        if time.minute != 30 and time.minute != 0:
            raise exceptions.ValidationError('Time should be 30 or 00 minutes')

        # check role of driver
        if id_driver.role != 'driver':
            raise exceptions.ValidationError('User should be a driver')

        serializer.save(startRoute=startRoute,
                        endRoute=endRoute, driver=id_driver)

    def perform_destroy(self, instance):
        instance.delete()


class ListCreateVanReservationView(generics.ListCreateAPIView):
    queryset = VanReservation.objects.all()
    serializer_class = VanReservationListSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        if self.request.user.role == 'admin':
            return VanReservation.objects.all()
        elif self.request.user.role == 'user':
            return VanReservation.objects.filter(user=self.request.user)
        elif self.request.user.role == 'driver':
            raise PermissionDenied('Driver can not access this page')
        else:
            raise PermissionDenied('User not found')


class SearchVanDriver(generics.ListAPIView):
    serializer_class = VanDriverSerializer
    permission_classes = [IsAuthenticated,]

    def get_queryset(self):
        startRoute = self.request.query_params.get('startRoute')
        endRoute = self.request.query_params.get('endRoute')
        date = self.request.query_params.get('date')

        startRoute = get_object_or_404(Locations, name=startRoute)
        endRoute = get_object_or_404(Locations, name=endRoute)

        queryset = VanDriver.objects.filter(
            startRoute=startRoute, endRoute=endRoute)

        if date:
            date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
            queryset = queryset.filter(date=date)

        return queryset
