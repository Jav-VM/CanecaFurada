"""
Datos ficticios de la demostración (Fase 13).

Todo es inventado: nombres y apellidos con «Proba», «Exemplo» o «Ficticio»,
calles «Rúa Ficticia», emails en el dominio reservado `demo.example.com`,
productos, cerveceras y recompensas marcados como demostración. Los códigos
postales son reales (A Coruña y alrededores) solo para las estadísticas
geográficas; no identifican a nadie.

Las fechas son desplazamientos en días respecto a la fecha de referencia de la
carga (`days=-30` = 30 días antes). Ver `builder.py`.
"""
import datetime
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

# --- Marcas que identifican los datos de demostración ---------------------------

DEMO_EMAIL_DOMAIN = "demo.example.com"
CATEGORY_SLUG_PREFIX = "demo-"
TEXT_PREFIX = "[DEMO]"
_NAMESPACE = uuid.UUID("fd2ebc55-b784-4c1c-83e3-9a2824608605")

# Solo desarrollo: nunca existe en producción (la app no está instalada allí).
# Se puede sustituir con la variable de entorno CANECA_DEMO_PASSWORD.
DEFAULT_PASSWORD = "Demo-Caneca-2026"


def demo_email(local_part):
    return f"{local_part}@{DEMO_EMAIL_DOMAIN}"


def demo_uuid(key):
    """`public_id` determinista de los objetos de demo (productos, eventos...)."""
    return uuid.uuid5(_NAMESPACE, key)


# --- Personas ----------------------------------------------------------------------


@dataclass(frozen=True)
class Staff:
    key: str
    first_name: str
    last_name: str
    joined: int
    deactivated: int | None = None


OWNER = Staff("propietaria", "Mariña", "Proba Demo", joined=-420)

EMPLOYEES = (
    Staff("brais.empregado", "Brais", "Exemplo Demo", joined=-400),
    Staff("uxia.empregada", "Uxía", "Ficticia Demo", joined=-300),
    Staff("iago.empregado", "Iago", "Proba Demo", joined=-200),
    # Antigua empleada: dada de baja por el propietario.
    Staff("noa.empregada", "Noa", "Exemplo Demo", joined=-380, deactivated=-90),
)


@dataclass(frozen=True)
class Customer:
    key: str
    first_name: str
    last_name: str
    joined: int
    date_of_birth: datetime.date | None  # None: se calcula (cumpleaños reciente)
    postal_code: str = "15001"
    city: str = "A Coruña"
    province: str = "A Coruña"
    country: str = "ES"
    street_number: int = 1
    address_line_2: str = ""
    phone: str = ""
    promo_email: bool = False
    promo_sms: bool = False
    verify: bool = True
    visits: int = 0  # compras "normales" repartidas entre el alta y ayer
    deactivated: int | None = None


BIRTHDAY_DAYS_AGO = 20

CUSTOMERS = (
    Customer("lua.proba", "Lúa", "Proba Demo", -390, datetime.date(1988, 5, 12), "15001", street_number=3,
             address_line_2="3º B", phone="600 000 011", promo_email=True, promo_sms=True, visits=9),
    Customer("martin.exemplo", "Martín", "Exemplo Demo", -370, datetime.date(1985, 11, 3), "15002",
             street_number=5, promo_email=True, visits=6),
    Customer("carme.ficticia", "Carme", "Ficticia Demo", -350, datetime.date(1979, 1, 21), "15003",
             street_number=7, phone="600 000 013", visits=5),
    Customer("xoan.proba", "Xoán", "Proba Demo", -330, datetime.date(1992, 7, 30), "15004",
             street_number=9, promo_email=True, visits=5),
    Customer("sabela.exemplo", "Sabela", "Exemplo Demo", -300, datetime.date(1995, 2, 14), "15005",
             street_number=11, visits=5),
    Customer("roi.ficticio", "Roi", "Ficticio Demo", -280, datetime.date(1983, 9, 9), "15006",
             street_number=13, promo_email=True, visits=4),
    Customer("iria.proba", "Iria", "Proba Demo", -260, datetime.date(1990, 4, 18), "15007",
             street_number=15, visits=4),
    Customer("anxo.exemplo", "Anxo", "Exemplo Demo", -240, datetime.date(1987, 12, 1), "15008",
             street_number=17, visits=3),
    Customer("alba.ficticia", "Alba", "Ficticia Demo", -220, datetime.date(1998, 6, 25), "15009",
             street_number=19, promo_email=True, visits=3),
    # Cumpleaños hace BIRTHDAY_DAYS_AGO días: recibe el regalo de puntos.
    Customer("breixo.proba", "Breixo", "Proba Demo", -200, None, "15010", street_number=21,
             promo_email=True, visits=3),
    # Nacida un 29 de febrero.
    Customer("olalla.exemplo", "Olalla", "Exemplo Demo", -180, datetime.date(1996, 2, 29), "15011",
             street_number=23, visits=2),
    Customer("daniel.ficticio", "Daniel", "Ficticio Demo", -160, datetime.date(1982, 3, 8), "15142",
             city="Arteixo", street_number=25, phone="600 000 022", promo_email=True, promo_sms=True, visits=2),
    Customer("antia.exemplo", "Antía", "Exemplo Demo", -140, datetime.date(1993, 10, 10), "15173",
             city="Oleiros", street_number=27, visits=2),
    Customer("pablo.ficticio", "Pablo", "Ficticio Demo", -120, datetime.date(1989, 8, 17), "15670",
             city="Culleredo", street_number=29, visits=1),
    Customer("nerea.proba", "Nerea", "Proba Demo", -100, datetime.date(1994, 1, 5), "27001",
             city="Lugo", province="Lugo", street_number=31, visits=1),
    # Una sola compra pequeña: saldo insuficiente para cualquier recompensa.
    Customer("tiago.exemplo", "Tiago", "Exemplo Demo", -90, datetime.date(1991, 5, 22), "4700-001",
             city="Braga", province="Braga", country="PT", street_number=33),
    # Una compra de 0,99 € que no da puntos base (redondeo hacia abajo).
    Customer("maria.ficticia", "María", "Ficticia Demo", -88, datetime.date(1997, 9, 30), "15001",
             street_number=35),
    # Verificado, sin compras, sin reservas: saldo cero.
    Customer("hugo.proba", "Hugo", "Proba Demo", -45, datetime.date(2000, 3, 3), "15004", street_number=37),
    # Con historial y después dado de baja por el propietario.
    Customer("noelia.exemplo", "Noelia", "Exemplo Demo", -330, datetime.date(1986, 6, 6), "15002",
             street_number=39, visits=3, deactivated=-15),
    # Pendientes de verificar el email. `joined=0`: registrada una hora antes de la carga.
    Customer("xiana.pendente", "Xiana", "Proba Demo", 0, datetime.date(1999, 11, 11), "15003",
             street_number=41, verify=False),
    Customer("uxio.pendente", "Uxío", "Exemplo Demo", -40, datetime.date(1984, 4, 4), "15005",
             street_number=43, verify=False),
    Customer("lois.pendente", "Lois", "Ficticio Demo", -8, datetime.date(1990, 12, 24), "15006",
             street_number=45, verify=False),
)

# Pendiente que pidió que le reenviasen el enlace (el primero queda revocado).
RESEND_VERIFICATION = ("lois.pendente", -7)

# Importes de las compras "normales" (euros), elegidos de forma determinista.
VISIT_AMOUNTS = ("6.40", "9.80", "12.50", "14.90", "18.20", "22.60", "27.30", "33.50", "38.90", "46.70")

# Compras concretas para casos límite: (cliente, empleado, día, hora, importe).
SPECIAL_PURCHASES = (
    ("martin.exemplo", "brais.empregado", -75, 22, "1000.00"),  # máximo permitido
    ("maria.ficticia", "iago.empregado", -70, 20, "0.99"),  # 0 puntos base por redondeo
    ("tiago.exemplo", "uxia.empregada", -80, 21, "12.50"),
)

# --- Puntos -------------------------------------------------------------------------

# Reglas de conversión: (día, puntos por euro, nota).
LOYALTY_RULES = (
    (-410, "1.00", "Conversión inicial"),
    (-60, "1.50", "Más puntos por euro desde el otoño"),
)

# Ajustes del propietario: (clave, cliente, día, puntos, motivo).
ADJUSTMENTS = (
    ("xoan-incidencia", "xoan.proba", -100, 50, "Compensación por una incidencia en barra (demo)"),
    ("anxo-duplicado", "anxo.exemplo", -50, -15, "Corrección de puntos duplicados (demo)"),
    ("daniel-error", "daniel.ficticio", -30, 25, "Ajuste de prueba (demo)"),
)
# Ajuste que el propietario compensa después: (clave del ajuste, día, motivo).
REVERSALS = (("daniel-error", -28, "Ajuste introducido por error (demo)"),)

QR_ROTATIONS = (("lua.proba", -30),)

PREFERENCE_CHANGES = (("roi.ficticio", -50, False, False),)  # (cliente, día, email, sms)

# --- Promociones ----------------------------------------------------------------------


@dataclass(frozen=True)
class PromotionData:
    key: str
    name: str
    description: str
    kind: str
    bonus_type: str
    created: int
    starts: int
    ends: int | None = None
    fixed_points: int | None = None
    multiplier: str | None = None
    min_purchase_amount: str | None = None
    max_uses_per_customer: int | None = None
    max_total_uses: int | None = None
    status: str = "ACTIVE"
    status_changes: tuple = ()  # ((día, estado), ...)


PROMOTIONS = (
    PromotionData("benvida", "Bono de benvida (demo)", "20 puntos extra en tu primera compra.", "PURCHASE",
                  "FIXED_POINTS", created=-366, starts=-365, fixed_points=20, max_uses_per_customer=1),
    PromotionData("dobres", "Puntos dobres de primavera (demo)", "Puntos dobles en compras desde 15 €.",
                  "PURCHASE", "MULTIPLIER", created=-245, starts=-240, ends=-200, multiplier="2.00",
                  min_purchase_amount="15.00", status_changes=((-199, "ENDED"),)),
    PromotionData("martes", "Martes de cata (demo)", "15 puntos extra por compra.", "PURCHASE", "FIXED_POINTS",
                  created=-101, starts=-100, fixed_points=15, max_total_uses=30, status_changes=((-50, "PAUSED"),)),
    PromotionData("reis", "Noite de Reis (demo)", "Borrador para una promoción futura.", "PURCHASE",
                  "FIXED_POINTS", created=-5, starts=60, ends=75, fixed_points=30, status="DRAFT"),
    PromotionData("aniversario", "Regalo de cumpleaños (demo)", "50 puntos el día de tu cumpleaños.",
                  "BIRTHDAY", "FIXED_POINTS", created=-380, starts=-380, fixed_points=50),
)

# --- Carta ------------------------------------------------------------------------------

# (slug sin prefijo, nombre, descripción, orden, publicada)
CATEGORIES = (
    ("casa", "Cervezas de la casa", "Elaboradas para la demostración.", 1, True),
    ("invitadas", "Cervezas invitadas", "Cerveceras ficticias invitadas.", 2, True),
    ("temporada", "De temporada", "Cervezas rotativas.", 3, True),
    ("picar", "Para picar", "Tapas y raciones.", 4, True),
    ("sen-alcol", "Sin alcohol y refrescos", "", 5, True),
    ("proximamente", "Próximamente", "Categoría oculta en la web.", 6, False),
)

STYLE_NAMES = ("IPA", "Pale Ale", "Stout", "Porter", "Lager", "Pilsner", "Saison", "Weissbier", "Sour", "Barley Wine")


@dataclass(frozen=True)
class ProductData:
    key: str
    category: str
    kind: str
    name: str
    price: str
    style: str | None = None
    abv: str | None = None
    serving: str = ""
    brewery: str = ""
    description: str = ""
    status: str = "PUBLISHED"
    available: bool = True
    featured: bool = False
    image: str | None = None  # color del placeholder


_BEER = "Cerveza de demostración."
PRODUCTS = (
    ProductData("furada-ipa", "casa", "HOUSE_BEER", "Furada IPA", "4.50", "IPA", "6.2", "Pinta",
                description=_BEER + " Amarga y cítrica.", featured=True, image="#e0a100"),
    ProductData("marola", "casa", "HOUSE_BEER", "Marola Pale Ale", "3.80", "Pale Ale", "5.0", "Caña",
                description=_BEER, featured=True, image="#d98e04"),
    ProductData("faro-negro", "casa", "HOUSE_BEER", "Faro Negro", "4.20", "Stout", "5.8", "Pinta",
                description=_BEER + " Tostada, con notas de café.", image="#3b2a1a"),
    ProductData("orballo", "casa", "HOUSE_BEER", "Orballo Lager", "3.20", "Lager", "4.6", "Caña",
                description=_BEER),
    ProductData("ardora", "casa", "HOUSE_BEER", "Ardora Saison", "4.80", "Saison", "6.5", "33 cl",
                description=_BEER, available=False),
    ProductData("bretema", "casa", "HOUSE_BEER", "Brétema Barley Wine", "6.50", "Barley Wine", "10.5", "20 cl",
                description=_BEER + " En preparación.", status="DRAFT"),
    ProductData("lupulo-dipa", "invitadas", "GUEST_BEER", "Lúpulo Ficticio DIPA", "5.50", "IPA", "8.0", "33 cl",
                brewery="Fábrica Imaxinaria (demo)", description=_BEER, featured=True),
    ProductData("pilsner-norte", "invitadas", "GUEST_BEER", "Pilsner do Norte", "3.90", "Pilsner", "4.9",
                "Caña", brewery="Cervexas Proba (demo)", description=_BEER),
    ProductData("porter-inverno", "invitadas", "GUEST_BEER", "Porter de Inverno", "4.60", "Porter", "6.0",
                "Pinta", brewery="Cervexas Proba (demo)", description=_BEER + " Ya no se sirve.", status="ARCHIVED"),
    ProductData("sour-arandos", "temporada", "ROTATING_BEER", "Sour de Arandos", "4.90", "Sour", "4.2", "33 cl",
                description=_BEER, image="#8e2c48"),
    ProductData("weiss-outono", "temporada", "ROTATING_BEER", "Weiss de Outono", "4.30", "Weissbier", "5.3",
                "Pinta", description=_BEER, available=False),
    ProductData("queixos", "picar", "FIXED", "Tabla de queixos (demo)", "12.00", serving="Ración",
                description="Producto de demostración."),
    ProductData("pementos", "picar", "FIXED", "Pementos de Padrón (demo)", "6.50", serving="Ración",
                description="Producto de demostración."),
    ProductData("empanada", "picar", "FIXED", "Empanada do día (demo)", "4.00", serving="Porción",
                description="Producto de demostración.", image="#b5651d"),
    ProductData("bravas", "picar", "FIXED", "Patacas bravas (demo)", "5.50", serving="Ración",
                description="Producto de demostración.", status="DRAFT"),
    ProductData("sen-alcol", "sen-alcol", "FIXED", "Cerveza sin alcohol (demo)", "3.00", abv="0.0", serving="33 cl"),
    ProductData("refresco", "sen-alcol", "FIXED", "Refresco (demo)", "2.50", serving="33 cl"),
    ProductData("imperial", "proximamente", "HOUSE_BEER", "Imperial Stout (demo)", "5.90", "Stout", "9.5",
                "20 cl", description=_BEER + " Publicada, pero su categoría está oculta."),
)

TAP_MENU = {
    "title": f"{TEXT_PREFIX} Carta de grifos",
    "text_alternative": (
        "Carta de grifos de demostración: Furada IPA, Marola Pale Ale, Faro Negro, Orballo Lager, "
        "Lúpulo Ficticio DIPA y Pilsner do Norte."
    ),
    "day": -10,
}

# --- Recompensas ----------------------------------------------------------------------


@dataclass(frozen=True)
class RewardData:
    key: str
    name: str
    description: str
    points_cost: int
    created: int
    status: str = "ACTIVE"
    stock: int | None = None
    position: int = 0
    image: str | None = None
    status_changes: tuple = ()


REWARDS = (
    RewardData("cana", "Caña de la casa", "Una caña de cualquier cerveza de la casa (demo).", 60, -380,
               position=1, image="#e0a100"),
    RewardData("pinta", "Pinta de la casa", "Una pinta de cerveza de la casa (demo).", 100, -380, position=2),
    RewardData("vaso", "Vaso serigrafiado", "Vaso de demostración.", 150, -300, position=3,
               status_changes=((-30, "PAUSED"),)),
    RewardData("tabla", "Tabla de queixos", "Ración para compartir (demo).", 250, -200, stock=5, position=4),
    RewardData("camiseta", "Camiseta (demo)", "Última unidad: se agota con el canje.", 500, -200, stock=1, position=5),
    RewardData("abrebotellas", "Abrebotellas (demo)", "Ya no se ofrece.", 40, -380, position=6,
               status_changes=((-100, "ARCHIVED"),)),
    RewardData("cata", "Cata privada (demo)", "Borrador de una recompensa futura.", 1200, -5, status="DRAFT",
               position=7),
)


@dataclass(frozen=True)
class RedemptionData:
    key: str
    customer: str
    reward: str
    requested: int
    validated: tuple | None = None  # (día, personal)
    cancelled: int | None = None
    expired: int | None = None  # día en que se ejecuta la caducidad


REDEMPTIONS = (
    RedemptionData("lua-cana", "lua.proba", "cana", -90, validated=(-88, "brais.empregado")),
    RedemptionData("lua-pinta", "lua.proba", "pinta", -20),  # pendiente
    RedemptionData("sabela-abre", "sabela.exemplo", "abrebotellas", -150, validated=(-149, "uxia.empregada")),
    RedemptionData("martin-tabla", "martin.exemplo", "tabla", -60, validated=(-59, "uxia.empregada")),
    RedemptionData("martin-vaso", "martin.exemplo", "vaso", -40, validated=(-39, "propietaria")),
    RedemptionData("martin-camiseta", "martin.exemplo", "camiseta", -10, validated=(-9, "iago.empregado")),
    RedemptionData("carme-cana", "carme.ficticia", "cana", -70, cancelled=-65),
    RedemptionData("xoan-pinta", "xoan.proba", "pinta", -55, expired=-24),
    RedemptionData("alba-cana", "alba.ficticia", "cana", -3),  # pendiente
)

# --- Eventos y reservas ------------------------------------------------------------------


@dataclass(frozen=True)
class EventData:
    key: str
    title: str
    summary: str
    created: int
    starts: int
    hour: int
    duration_hours: int | None = 2
    capacity: int | None = None
    accepts_reservations: bool = True
    featured: bool = False
    image: str | None = None
    publish: bool = True
    archived: int | None = None


EVENTS = (
    EventData("cata-primavera", "Cata de primavera (demo)", "Cata guiada de cervezas de temporada.",
              created=-200, starts=-170, hour=19, capacity=20, archived=-160),
    EventData("concerto-verao", "Concierto de verano (demo)", "Música en directo en la terraza.",
              created=-120, starts=-90, hour=21, accepts_reservations=False, archived=-80),
    EventData("cata-outono", "Cata de otoño (demo)", "Cervezas de otoño con maridaje.",
              created=-60, starts=-30, hour=19, capacity=12, image="#8e2c48", archived=-25),
    EventData("obradoiro", "Taller de elaboración (demo)", "Ya celebrado; sigue publicado.",
              created=-15, starts=-3, hour=18, accepts_reservations=False),
    EventData("cata-guiada", "Cata guiada (demo)", "Aforo de 10 personas, casi completo.",
              created=-20, starts=7, hour=19, capacity=10, featured=True, image="#e0a100"),
    EventData("musica-directo", "Música en directo (demo)", "Entrada libre, sin reserva.",
              created=-12, starts=14, hour=21, accepts_reservations=False, featured=True, image="#3b2a1a"),
    EventData("maridaxe", "Cena maridaje (demo)", "Cinco platos y cinco cervezas.",
              created=-20, starts=25, hour=21, duration_hours=3, capacity=30),
    EventData("magosto", "Magosto cervecero (demo)", "Castañas y cerveza, sin límite de plazas.",
              created=-10, starts=40, hour=18, duration_hours=4),
    EventData("noite-reis", "Noche de Reyes (demo)", "Borrador: aún no publicado.",
              created=-2, starts=80, hour=20, capacity=40, publish=False),
)


@dataclass(frozen=True)
class ReservationData:
    customer: str
    requested: int  # día de la solicitud
    party_size: int
    event: str | None = None
    table_day: int | None = None  # reservas de mesa: día y hora
    table_hour: int = 21
    notes: str = ""
    # Transiciones posteriores: ((día, acción, mensaje), ...). Acciones:
    # confirm, reject, cancel (propietario), cancel_own (cliente), complete.
    steps: tuple = field(default=())


RESERVATIONS = (
    # Evento pasado: completadas, rechazada y cancelada por el cliente.
    ReservationData("sabela.exemplo", -190, 2, "cata-primavera", steps=((-175, "confirm", ""), (-169, "complete", ""))),
    ReservationData("roi.ficticio", -188, 4, "cata-primavera", steps=((-175, "confirm", ""), (-169, "complete", ""))),
    ReservationData("iria.proba", -186, 2, "cata-primavera",
                    steps=((-176, "reject", "Lo sentimos, preferimos grupos ya confirmados."),)),
    ReservationData("anxo.exemplo", -185, 3, "cata-primavera", steps=((-180, "cancel_own", ""),)),
    # Evento pasado reciente: completadas, cancelada por el local y una confirmada sin completar.
    ReservationData("lua.proba", -50, 2, "cata-outono", steps=((-45, "confirm", ""), (-29, "complete", ""))),
    ReservationData("alba.ficticia", -48, 5, "cata-outono", notes="Celebramos un cumpleaños.",
                    steps=((-45, "confirm", "¡Os esperamos!"), (-29, "complete", ""))),
    ReservationData("breixo.proba", -47, 2, "cata-outono",
                    steps=((-35, "cancel", "Hemos reducido el aforo de la cata."),)),
    ReservationData("martin.exemplo", -46, 3, "cata-outono", steps=((-44, "confirm", ""),)),
    # Evento futuro casi completo: 9 de 10 plazas confirmadas y una solicitud pendiente.
    ReservationData("lua.proba", -18, 4, "cata-guiada", steps=((-9, "confirm", ""),)),
    ReservationData("martin.exemplo", -17, 3, "cata-guiada", steps=((-9, "confirm", ""),)),
    ReservationData("carme.ficticia", -16, 2, "cata-guiada", steps=((-8, "confirm", ""),)),
    # Pedida antes de llenarse: confirmarla ahora superaría el aforo.
    ReservationData("xoan.proba", -12, 2, "cata-guiada"),
    # Otros eventos futuros.
    ReservationData("sabela.exemplo", -5, 2, "maridaxe"),
    ReservationData("roi.ficticio", -6, 6, "maridaxe", steps=((-4, "confirm", ""),)),
    ReservationData("olalla.exemplo", -2, 2, "maridaxe"),
    ReservationData("daniel.ficticio", -3, 8, "magosto"),
    # Mesas pasadas.
    ReservationData("carme.ficticia", -100, 4, table_day=-98, steps=((-99, "confirm", ""), (-97, "complete", ""))),
    ReservationData("antia.exemplo", -45, 12, table_day=-40, table_hour=22,
                    steps=((-44, "reject", "Ese día el local está completo."),)),
    ReservationData("xoan.proba", -15, 2, table_day=-10, steps=((-12, "cancel_own", ""),)),
    ReservationData("noelia.exemplo", -60, 3, table_day=-58, steps=((-59, "confirm", ""), (-57, "complete", ""))),
    # Mesas futuras.
    ReservationData("lua.proba", -4, 2, table_day=2, table_hour=20, steps=((-3, "confirm", ""),)),
    ReservationData("iria.proba", -1, 2, table_day=3),
    ReservationData("anxo.exemplo", -2, 6, table_day=5, table_hour=20, steps=((-1, "confirm", ""),)),
    ReservationData("alba.ficticia", -3, 3, table_day=10,
                    steps=((-1, "cancel", "Ese día el local está cerrado por un evento privado."),)),
    ReservationData("pablo.ficticio", -1, 20, table_day=12, notes="Comida de empresa."),
)

# --- Campañas ------------------------------------------------------------------------------


@dataclass(frozen=True)
class CampaignData:
    key: str
    name: str
    subject: str
    body: str
    created: int
    queued: int | None = None
    cancelled: int | None = None


CAMPAIGNS = (
    CampaignData("outono", "Cervezas de otoño (demo)", "Llegan las cervezas de otoño",
                 "Mensaje de demostración: esta semana estrenamos las cervezas de temporada.", -36, queued=-34),
    CampaignData("descartada", "Campaña descartada (demo)", "Aviso de prueba",
                 "Mensaje de demostración que se canceló antes de enviarse.", -20, queued=-20, cancelled=-19),
    CampaignData("borrador", "Borrador de Navidad (demo)", "Navidad en la cervecería",
                 "Mensaje de demostración en borrador.", -5),
)


# --- Identificadores ---------------------------------------------------------------------


def demo_public_ids(prefix, items):
    return [demo_uuid(f"{prefix}:{item.key}") for item in items]


def product_ids():
    return demo_public_ids("product", PRODUCTS)


def event_ids():
    return demo_public_ids("event", EVENTS)


def reward_ids():
    return demo_public_ids("reward", REWARDS)


def promotion_ids():
    return demo_public_ids("promotion", PROMOTIONS)


def campaign_ids():
    return demo_public_ids("campaign", CAMPAIGNS)


def decimal(value):
    return Decimal(value) if value is not None else None
