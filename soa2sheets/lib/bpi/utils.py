from typing import Optional

from datetime import datetime

class Currency:
  @classmethod
  def to_float(cls, text: Optional[str]) -> float:
    return float(text.replace(',', '')) if text else None
  
  @classmethod
  def to_text(cls, amount: float) -> str:
    return f'{amount:,.2f}'
  
  @classmethod
  def to_symbol(cls, text: Optional[str]) -> str:
    if not text:
      return 'PHP'

    symbol = text.replace(' ', '')

    if symbol == 'Yen':
      return 'JPY'
    if symbol == 'Baht':
      return 'THB'
    if symbol == 'Euro':
      return 'EUR'
    if symbol == 'U.S.Dollar':
      return 'USD'
    
    return symbol
  
class Date:
  @classmethod
  def to_datetime(cls, text: str, format = '%B %d,%Y') -> datetime:
    try:
      return datetime.strptime(text, format)
    except ValueError:
      return datetime.strptime(text, format.replace(' ', ''))

  @classmethod
  def to_text(cls, date: datetime, format = '%m/%d/%Y') -> str:
    return date.strftime(format)
