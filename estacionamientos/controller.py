# -*- coding: utf-8 -*-

# Archivo con funciones de control para SAGE
from estacionamientos.models import Estacionamiento, Reserva, Pago
from datetime import datetime, timedelta, time
from decimal import Decimal
from collections import OrderedDict

# chequeo de horarios de extended
def HorarioEstacionamiento(HoraInicio, HoraFin):
	return HoraFin > HoraInicio

def validarHorarioReserva(inicioReserva, finReserva, apertura, cierre, max_dias):
	if inicioReserva >= finReserva:
		return (False, 'El horario de inicio de reservacion debe ser menor al horario de fin de la reserva.')
	if finReserva - inicioReserva < timedelta(hours=1):
		return (False, 'El tiempo de reserva debe ser al menos de 1 hora.')
	if inicioReserva.date() < datetime.now().date():
		return (False, 'La reserva no puede tener lugar en el pasado.')
	if finReserva.date() > (datetime.now()+timedelta(days=max_dias -1)).date():
		return (False, 'La reserva debe estar dentro de los próximos ' + str(max_dias) + ' días.')
	if apertura.hour==0 and apertura.minute==0 \
		and cierre.hour==23 and cierre.minute==59:
		horizonte_reserva=timedelta(days=max_dias)
		if finReserva-inicioReserva<=horizonte_reserva :
			return (True,'')
		else:
			return(False,'Se puede reservar un puesto por un maximo de ' + str(max_dias) + ' días.')
	else:
		hora_inicio = time(hour = inicioReserva.hour, minute = inicioReserva.minute)
		hora_final  = time(hour = finReserva.hour   , minute = finReserva.minute)
		if hora_inicio<apertura:
			return (False, 'El horario de inicio de reserva debe estar en un horario válido.')
		if hora_final > cierre:
			return (False, 'El horario de fin de la reserva debe estar en un horario válido.')
		if inicioReserva.date()!=finReserva.date():
			return (False, 'No puede haber reservas entre dos días distintos')
		return (True,'')

def marzullo(idEstacionamiento, hIn, hOut, tipoVehiculo):
	e = Estacionamiento.objects.get(id = idEstacionamiento)
	ocupacion = []
	if tipoVehiculo == 'Moto':
		capacidad = e.capacidad_motos
	elif tipoVehiculo == 'Carro':
		capacidad = e.capacidad_carros
	elif tipoVehiculo == 'Camion':
		capacidad = e.capacidad_camiones
	elif tipoVehiculo == 'Vehículo Especial':
		capacidad = e.capacidad_especiales

	for reserva in e.reserva_set.filter(tipoVehiculo = tipoVehiculo):
		ocupacion += [(reserva.inicioReserva, 1), (reserva.finalReserva, -1)]
	ocupacion += [(hIn, 1), (hOut, -1)]

	count = 0
	for r in sorted(ocupacion):
		count += r[1]
		if count > capacidad:
			return False
	return True

def splitDates(inicio,final,listaFeriados):
	horarioSplit = [[],[]]
	inicioIntervalo = inicio
	tiempoActual = inicio
	while tiempoActual <=final:
		tipo = 0
		for dia in listaFeriados:
			if tiempoActual.month == dia.fecha.month and tiempoActual.day == dia.fecha.day:
				tipo =  1
		if tiempoActual.month == final.month and tiempoActual.day == final.day:
			horarioSplit[tipo].append([inicioIntervalo,final])
			tiempoActual = final
		else:
			tiempoActual =datetime.strptime(('{2}-{1}-{0}/23:59').format(tiempoActual.day,tiempoActual.month,tiempoActual.year),"%Y-%m-%d/%H:%M")
			tipoActual = 0
			for dia in listaFeriados:
				if (tiempoActual + timedelta(minutes=1)).month == dia.fecha.month and (tiempoActual + timedelta(minutes=1)).day == dia.fecha.day:
					tipoActual =  1
			if tipo != tipoActual:
				horarioSplit[tipo].append([inicioIntervalo,tiempoActual + timedelta(minutes=1)])
				inicioIntervalo = tiempoActual + timedelta(minutes=1)
		tiempoActual += timedelta(minutes=1)	
	return horarioSplit

def get_client_ip(request):
	x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
	if x_forwarded_for:
		ip = x_forwarded_for.split(',')[-1].strip()
	else:
		ip = request.META.get('REMOTE_ADDR')
	return ip

def tasa_reservaciones(id_estacionamiento,prt=False):
	e = Estacionamiento.objects.get(id = id_estacionamiento)
	ahora = datetime.today().replace(hour=0,minute=0,second=0,microsecond=0)
	reservas_filtradas = e.reserva_set.filter(finalReserva__gt=ahora)
	lista_fechas=[(ahora+timedelta(i)).date() for i in range(e.horizonte_reserva)]
	lista_valores=[0 for i in range(e.horizonte_reserva)]
	ocupacion_por_dia = OrderedDict(zip(lista_fechas,lista_valores))
	UN_DIA = timedelta(days = 1)
	
	for reserva in reservas_filtradas:
		# Caso del inicio de la reserva
		if (reserva.inicioReserva < ahora):
			reserva_inicio = ahora
		else:
			reserva_inicio = reserva.inicioReserva
		reserva_final = reserva.finalReserva
		final_aux=reserva_inicio.replace(hour=0,minute=0,second=0,microsecond=0)
		while (reserva_final.date()>reserva_inicio.date()): 
			final_aux+=UN_DIA
			longitud_reserva = final_aux-reserva_inicio
			ocupacion_por_dia[reserva_inicio.date()] += longitud_reserva.seconds/60+longitud_reserva.days*24*60
			reserva_inicio = final_aux
		longitud_reserva=reserva_final-reserva_inicio
		ocupacion_por_dia[reserva_inicio.date()] += longitud_reserva.seconds/60 + longitud_reserva.days*24*60
			
	return ocupacion_por_dia

def calcular_porcentaje_de_tasa(hora_apertura,hora_cierre, capacidad, ocupacion):
	factor_divisor=timedelta(hours=hora_cierre.hour,minutes=hora_cierre.minute)
	factor_divisor-=timedelta(hours=hora_apertura.hour,minutes=hora_apertura.minute)
	factor_divisor=Decimal(factor_divisor.seconds)/Decimal(60)
	if (hora_apertura==time(0,0) and hora_cierre==time(23,59)):
		factor_divisor+=1 # Se le suma un minuto
	for i in ocupacion.keys():
		ocupacion[i]=(Decimal(ocupacion[i])*100/(factor_divisor*capacidad)).quantize(Decimal('1.0'))

def consultar_ingresos(rif):
	listaEstacionamientos = Estacionamiento.objects.filter(rif = rif)
	ingresoTotal = 0
	listaIngresos = []

	for estacionamiento in listaEstacionamientos:
		listaFacturas = Pago.objects.filter(reserva__estacionamiento__nombre = estacionamiento.nombre).filter(estado = True)
		ingreso       = [estacionamiento.nombre, 0]
		for factura in listaFacturas:
			ingreso[1] += factura.monto
		listaIngresos += [ingreso]
		ingresoTotal  += ingreso[1]

	return listaIngresos, ingresoTotal
