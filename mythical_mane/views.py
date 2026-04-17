from datetime import date, datetime
from decimal import Decimal

from django.apps import apps
from django.http import Http404
from django.shortcuts import render


ROW_LIMIT = 200


EXCLUDED_TABLE_PREFIXES = ("auth_", "django_")


def _get_table_model(table_slug):
	app_models = apps.get_app_config("mythical_mane").get_models()
	for model in app_models:
		if _is_excluded_table(model._meta.db_table):
			continue
		if model._meta.db_table == table_slug:
			return model
	return None


def _is_excluded_table(table_name):
	return table_name.startswith(EXCLUDED_TABLE_PREFIXES)


def _default_columns(model):
	columns = []
	for field in model._meta.fields:
		if field.many_to_one and field.concrete:
			related_model = field.related_model
			related_field_names = {f.name for f in related_model._meta.fields}
			if "name" in related_field_names:
				accessor = f"{field.name}__name"
			elif "username" in related_field_names:
				accessor = f"{field.name}__username"
			else:
				accessor = field.attname
		else:
			accessor = field.name

		columns.append({"accessor": accessor, "label": field.verbose_name.title()})

	return columns[:6]


def _format_value(value):
	if value is None or value == "":
		return "-"
	if isinstance(value, datetime):
		return value.strftime("%Y-%m-%d %H:%M")
	if isinstance(value, date):
		return value.strftime("%Y-%m-%d")
	if isinstance(value, Decimal):
		return f"{value}"
	return str(value)


def _read_accessor(obj, accessor):
	value = obj
	for attr in accessor.split("__"):
		value = getattr(value, attr, None)
		if value is None:
			return "-"
	return _format_value(value)


def _model_title(model):
	return model._meta.db_table.replace("_", " ").title()


def table_index(request):
	app_models = sorted(
		[
			model
			for model in apps.get_app_config("mythical_mane").get_models()
			if not _is_excluded_table(model._meta.db_table)
		],
		key=lambda model: model._meta.db_table,
	)
	tables = [
		{"slug": model._meta.db_table, "title": _model_title(model)}
		for model in app_models
	]
	return render(request, "mythical_mane/table_index.html", {"tables": tables})


def table_list(request, table_slug):
	model = _get_table_model(table_slug)
	if model is None:
		raise Http404("Table not found")

	custom_columns = {
		"patient": [
			{"accessor": "name", "label": "Patient"},
			{"accessor": "color", "label": "Color"},
			{"accessor": "dob", "label": "Date of Birth"},
			{"accessor": "owner__name", "label": "Owner"},
			{"accessor": "universe__name", "label": "Universe"},
		],
		"care_note": [
			{"accessor": "care_note_id", "label": "ID"},
			{"accessor": "patient__name", "label": "Patient"},
			{"accessor": "note_text", "label": "Note"},
			{"accessor": "follow_up_date", "label": "Follow Up"},
			{"accessor": "resolved", "label": "Resolved"},
			{"accessor": "created_at", "label": "Created"},
		],
	}
	columns = custom_columns.get(table_slug, _default_columns(model))

	select_related_fields = []
	for column in columns:
		first_attr = column["accessor"].split("__", 1)[0]
		try:
			field = model._meta.get_field(first_attr)
			if field.many_to_one:
				select_related_fields.append(first_attr)
		except Exception:
			continue

	queryset = model.objects.all()
	if select_related_fields:
		queryset = queryset.select_related(*sorted(set(select_related_fields)))

	rows = []
	for obj in queryset[:ROW_LIMIT]:
		rows.append([_read_accessor(obj, column["accessor"]) for column in columns])

	context = {
		"table_slug": table_slug,
		"table_title": _model_title(model),
		"columns": columns,
		"rows": rows,
		"row_count": len(rows),
		"row_limit": ROW_LIMIT,
	}
	return render(request, "mythical_mane/table_list.html", context)


def patient_list(request):
	return table_list(request, "patient")
