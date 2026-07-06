from aiogram.fsm.state import State, StatesGroup


class AddByCode(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_twofa = State()


class AddByBulkCode(StatesGroup):
    waiting_bulk_input = State()


class AddByZip(StatesGroup):
    waiting_zip = State()
