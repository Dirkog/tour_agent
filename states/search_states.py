"""
Состояния FSM (Finite State Machine) для диалога поиска тура.
Каждое состояние соответствует одному шагу сбора параметров.
"""
from aiogram.fsm.state import State, StatesGroup


class SearchStates(StatesGroup):
    """Состояния диалога поиска тура."""

    # Ожидание страны/направления назначения
    WAITING_COUNTRY = State()

    # Ожидание дат поездки (вылет и возврат)
    WAITING_DATES = State()

    # Ожидание количества гостей (взрослые + дети)
    WAITING_GUESTS = State()

    # Ожидание бюджета
    WAITING_BUDGET = State()

    # Ожидание дополнительных предпочтений (звёзды, питание, пляж)
    WAITING_PREFERENCES = State()

    # Ожидание города вылета
    WAITING_DEPARTURE = State()

    # Подтверждение параметров перед поиском
    CONFIRMING_PARAMS = State()


class OfferStates(StatesGroup):
    """Состояния работы с готовым предложением."""

    # Ожидание ввода отредактированного текста предложения
    EDITING_OFFER = State()


class RegisterStates(StatesGroup):
    """Состояния регистрации агента."""

    # Ожидание выбора типа организации
    WAITING_ORG_TYPE = State()
