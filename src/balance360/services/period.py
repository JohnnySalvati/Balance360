import calendar
from datetime import date


def resolve_period(
    year: int | None = None,
    month: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[date, date]:

    if date_from or date_to:
        if date_from and date_to and date_from > date_to:
            raise ValueError("La fecha desde no puede ser mayor que la fecha hasta.")
        return (date_from or date(day=1, month=1, year=1900), date_to or date.today())

    if year and month:
        return (
            date(day=1, month=month, year=year),
            date(day=calendar.monthrange(year, month)[1], month=month, year=year),
        )

    if year:
        return (date(day=1, month=1, year=year), date(day=31, month=12, year=year))
    return (date(day=1, month=1, year=1900), date.today())
