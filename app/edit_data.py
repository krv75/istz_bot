from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
import os
import app.keyboards as kb
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime


from app.state import EditDateSession, EditDeadline, EditCertification, EditTeacher, EditSchedule
from app.database.models import db

load_dotenv()
edit_data = Router()

ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
HEADMAN_ID = int(os.getenv("HEADMAN_ID", 0))

admin_ids = [ADMIN_ID, HEADMAN_ID]

async def is_admin(user_id: int) -> bool:
    return user_id in admin_ids

@edit_data.message(Command('edit_data'))
async def admin_panel(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен.", reply_markup=kb.kb_main_menu)
        return
    await message.answer("Панель редактирования данных.\nВыберите действие:",
        reply_markup=kb.kb_edit_data)


@edit_data.callback_query(F.data == 'edit_data')
async def admin_panel(callback: CallbackQuery):
    await callback.message.answer("Панель администратора.\nВыберите действие:",
        reply_markup=kb.kb_edit_data)


# РЕДАКТИРОВАНИЕ ДАННЫХ О СРОКАХ СЕССИИ
@edit_data.callback_query(F.data == 'edit_date_session')
async def edit_name_session(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите новое название семестра:")
    await state.set_state(EditDateSession.edit_name)

@edit_data.message(EditDateSession.edit_name)
async def save_name_session(message: Message, state: FSMContext):
    await state.update_data(name_session=message.text)
    await message.answer("Введите новую дату начала семестра:")
    await state.set_state(EditDateSession.edit_start_date)

@edit_data.message(EditDateSession.edit_start_date)
async def save_start_date(message: Message, state: FSMContext):
    await state.update_data(start_date=message.text)
    await message.answer("Введите новую дату окончания сессии:")
    await state.set_state(EditDateSession.edit_end_date)

@edit_data.message(EditDateSession.edit_end_date)
async def save_end_date(message: Message, state: FSMContext):
    await state.update_data(end_date=message.text)

    data = await state.get_data()

    await db.pool.execute('''
    UPDATE session_periods SET name = $1, start_date = $2, end_date = $3
    ''', data['name_session'], data['start_date'], data['end_date'])

    await message.answer("✅ Данные о сроках проведения сессии изменены", reply_markup=kb.back_edit_data)
    await state.clear()


# РЕДАКТИРОВАНИЕ ДАННЫХ ПО ДЭДЛАЙНАМ
@edit_data.callback_query(F.data == 'view_deadlines')
async def view_deadlines(callback: CallbackQuery):
    rows = await db.pool.fetch("SELECT id, subject_name, deadline_date FROM deadlines ORDER BY id ASC")

    if not rows:
        await callback.message.answer("❌ Нет данных о задачах.", reply_markup=kb.back_edit_data)
        return

    kb_view_deadlines = InlineKeyboardBuilder()
    for row in rows:
        text = f"{row['subject_name']} — {row['deadline_date']}"
        kb_view_deadlines.button(text=text, callback_data=f"edit_deadline_{row['id']}")

    kb_view_deadlines.adjust(1)
    await callback.message.answer("📋 Список задач:", reply_markup=kb_view_deadlines.as_markup())


@edit_data.callback_query(F.data.startswith('edit_deadline_'))
async def edit_deadline(callback: CallbackQuery, state: FSMContext):
    deadline_id = int(callback.data.split('_')[-1])
    await state.update_data(deadline_id=deadline_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="📘 Задача", callback_data="edit_field_subject")
    kb.button(text="📅 Срок", callback_data="edit_field_date")
    kb.button(text="📝 Описание", callback_data="edit_field_description")
    kb.button(text="⬅️ Назад", callback_data="view_deadlines")
    kb.adjust(1)

    await callback.message.edit_text(
        "Что вы хотите изменить?",
        reply_markup=kb.as_markup()
    )


@edit_data.callback_query(F.data.startswith("edit_field_"))
async def choose_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split("_")[-1]
    await state.update_data(edit_field=field)

    field_names = {
        "subject": "новое название предмета",
        "date": "новый срок сдачи",
        "description": "новое описание задачи"
    }

    await callback.message.edit_text(f"Введите {field_names[field]}:")
    await state.set_state(EditDeadline.waiting_for_edit_value)


@edit_data.message(EditDeadline.waiting_for_edit_value)
async def save_edit(message: Message, state: FSMContext):
    data = await state.get_data()
    deadline_id = data["deadline_id"]
    field = data["edit_field"]
    new_value = message.text

    column_map = {
        "subject": "subject_name",
        "date": "deadline_date",
        "description": "description"
    }
    column_name = column_map[field]

    await db.pool.execute(f'''
        UPDATE deadlines
        SET {column_name} = $1
        WHERE id = $2
    ''', new_value, deadline_id)

    await message.answer("✅ Изменения успешно сохранены.", reply_markup=kb.kb_edit_data)
    await state.clear()

# РЕДАКТИРОВАНИЕ ГРАФИКА ПРОВЕДЕНИЯ ЗАЧЕТОВ И ЭКЗАМЕНОВ
@edit_data.callback_query(F.data == 'view_certification')
async def view_certification(callback: CallbackQuery):
    rows = await db.pool.fetch('''
    SELECT id, certification, subject_name, exam_date, teacher_name 
    FROM exams_schedule 
    ORDER BY id ASC
    ''')
    if not rows:
        await callback.message.answer("❌ Данные отсутствуют", reply_markup=kb.kb_edit_data)
        return

    kb_view_certification = InlineKeyboardBuilder()
    for row in rows:
        text = f"{row['certification']} - {row['subject_name']}"
        kb_view_certification.button(text=text, callback_data=f"edit_certification_{row['id']}")

    kb_view_certification.adjust(1)
    await callback.message.answer("📋 Список зачетов и экзаменов:", reply_markup=kb_view_certification.as_markup())


# Функция для выбора аттестации для редактирования
@edit_data.callback_query(F.data.startswith('edit_certification_'))
async def edit_certification(callback: CallbackQuery, state: FSMContext):
    certification_id = int(callback.data.split('_')[-1])
    await state.update_data(certification_id=certification_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="Вид аттестации", callback_data='edit_f_certification')
    kb.button(text="Дата проведения аттестации", callback_data='edit_f_exam_date')
    kb.button(text="Название предмета", callback_data='edit_f_subject_name')
    kb.button(text="ФИО преподавателя", callback_data='edit_f_teacher_name')
    kb.button(text="⬅️ Назад", callback_data="view_certification")
    kb.adjust(1)

    await callback.message.edit_text("Что вы хотите изменить?", reply_markup=kb.as_markup())


# Функция для выбора поля, которое будем редактировать
@edit_data.callback_query(F.data.startswith('edit_f_'))
async def choose_edit_data(callback: CallbackQuery, state: FSMContext):
    # Берём всё после 'edit_f_'
    field = callback.data[len('edit_f_'):]
    await state.update_data(edit_field=field)

    field_name = {
        'certification': "Вид аттестации",
        'subject_name': "Название предмета",
        'exam_date': "Дата проведения аттестации",
        'teacher_name': "ФИО преподавателя"
    }

    if field not in field_name:
        await callback.message.answer("❌ Некорректное поле для редактирования.")
        return

    await callback.message.edit_text(f"Введите {field_name[field]}:")
    await state.set_state(EditCertification.edit_value)


# Функция для сохранения нового значения в базе
@edit_data.message(EditCertification.edit_value)
async def save_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    certification_id = data.get('certification_id')
    field = data.get("edit_field")
    new_value = message.text

    if not certification_id or not field:
        await message.answer("❌ Ошибка состояния. Попробуйте снова.")
        await state.clear()
        return

    column_map = {
        'certification': 'certification',
        'subject_name': 'subject_name',
        'exam_date': 'exam_date',
        'teacher_name': 'teacher_name'
    }

    if field not in column_map:
        await message.answer("❌ Некорректное поле для редактирования.")
        await state.clear()
        return

    column_name = column_map[field]

    await db.pool.execute(f'''
        UPDATE exams_schedule
        SET {column_name} = $1
        WHERE id = $2
    ''', new_value, certification_id)

    await message.answer("✅ Изменения успешно сохранены.", reply_markup=kb.kb_edit_data)
    await state.clear()



# РЕДАКТИРОВАНИЕ ФИО ПРЕПОДАВАТЕЛЕЙ
@edit_data.callback_query(F.data == 'view_teacher')
async def view_teacher(callback: CallbackQuery):
    rows = await db.pool.fetch('''
    SELECT id, subject_name, teacher_name 
    FROM teacher
    ORDER BY subject_name ASC
    ''')

    if not rows:
        await callback.message.answer("❌ Данные отсутствуют", reply_markup=kb.kb_edit_data)
        return

    kb_view_teacher = InlineKeyboardBuilder()
    for row in rows:
        text = f"{row['subject_name']} - {row['teacher_name']}"
        kb_view_teacher.button(text=text, callback_data=f"edit_teacher_{row['id']}")

    kb_view_teacher.adjust(1)
    await callback.message.answer("📋 По предметный список преподавателей:", reply_markup=kb_view_teacher.as_markup())

@edit_data.callback_query(F.data.startswith('edit_teacher_'))
async def edit_deadline(callback: CallbackQuery, state: FSMContext):
    teacher_id = int(callback.data.split('_')[-1])
    await state.update_data(teacher_id=teacher_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="ФИО преподавателя", callback_data="edit_fio")
    kb.button(text="Учебный предмет", callback_data="edit_subject")
    kb.button(text="⬅️ Назад", callback_data="view_teacher")
    kb.adjust(1)

    await callback.message.edit_text(
        "Что вы хотите изменить?",
        reply_markup=kb.as_markup()
    )


# РЕДАКТИРОВАНИЕ РАСПИСАНИЯ ЗАНЯТИЙ
@edit_data.callback_query(F.data == "edit_schedule")
async def edit_schedule(callback: CallbackQuery):
    kb_type = InlineKeyboardBuilder()
    kb_type.button(text="🗓 Удалить по дате", callback_data="delete_schedule_daily")
    kb_type.adjust(1)

    await callback.message.answer(
        "Выберите удаление расписания по дате:",
        reply_markup=kb_type.as_markup()
    )


# ================= Удаление по дате =================
@edit_data.callback_query(F.data == "delete_schedule_daily")
async def choose_date_for_delete(callback: CallbackQuery):
    # Получаем все даты с занятиями
    rows = await db.pool.fetch("SELECT DISTINCT day_of_week FROM schedule ORDER BY day_of_week ASC")

    if not rows:
        await callback.message.answer("❌ Нет данных для удаления", reply_markup=kb.kb_edit_data)
        return

    kb_dates = InlineKeyboardBuilder()
    for row in rows:
        date_str = row['day_of_week']
        kb_dates.button(text=date_str, callback_data=f"edit_date_{date_str}")
    kb_dates.button(text="🔙 Назад", callback_data="edit_schedule")
    kb_dates.adjust(1)

    await callback.message.answer("Выберите дату для удаления всех занятий:", reply_markup=kb_dates.as_markup())


@edit_data.callback_query(F.data.startswith("edit_date_"))
async def delete_lessons_by_date(callback: CallbackQuery):
    date_str = callback.data.replace("edit_date_", "")
    rows = await db.pool.fetch("SELECT id FROM schedule WHERE day_of_week = $1", date_str)

    if not rows:
        formatted_date = datetime.strptime(date_str, "%d.%m").strftime("%d.%m")
        await callback.message.answer(
            f"❌ Нет данных на {formatted_date}",
            reply_markup=kb.kb_edit_data
        )
        return

    kb_confirm = InlineKeyboardBuilder()
    kb_confirm.button(text="✅ Удалить все занятия", callback_data=f"confirm_delete_date_{date_str}")
    kb_confirm.button(text="🔙 Отмена", callback_data="delete_schedule_daily")
    kb_confirm.adjust(1)

    formatted_date = datetime.strptime(date_str, "%d.%m").strftime("%d.%m")
    await callback.message.answer(
        f"Вы действительно хотите удалить все занятия на {formatted_date}?",
        reply_markup=kb_confirm.as_markup()
    )


@edit_data.callback_query(F.data.startswith("confirm_delete_date_"))
async def perform_delete_date(callback: CallbackQuery):
    date_str = callback.data.replace("confirm_delete_date_", "")
    await db.pool.execute("DELETE FROM schedule WHERE day_of_week = $1", date_str)
    formatted_date = datetime.strptime(date_str, "%d.%m").strftime("%d.%m")
    await callback.message.answer(
        f"✅ Все занятия на {formatted_date} удалены",
        reply_markup=kb.kb_edit_data
    )