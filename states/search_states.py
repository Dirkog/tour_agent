"""FSM-состояния бота."""
from aiogram.fsm.state import State, StatesGroup


class RegisterStates(StatesGroup):
    WAITING_ORG_TYPE = State()


class SearchStates(StatesGroup):
    WAITING_COUNTRY = State()
    WAITING_CITY = State()
    WAITING_DATES = State()
    WAITING_GUESTS = State()
    WAITING_BUDGET = State()
    WAITING_PREFERENCES = State()
    WAITING_DEPARTURE = State()
    CONFIRMING_PARAMS = State()


class OfferStates(StatesGroup):
    EDITING_OFFER = State()
