from datetime import datetime

from typing import List, Optional
from types import SimpleNamespace
from enum import Enum

import re

from .utils import Currency, Date

MONTH_REGEX = r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
AMOUNT_REGEX = r'(-?(\d{1,3},)*\d{1,3}\.\d{2})'
SIP_REGEX = r'(Ro|Sip\-Pa)'

class BpiStatementInfo(SimpleNamespace):
  customer_number: str
  statement_date: datetime
  due_date: datetime

  credit_limit: float
  total_due: float
  minimum_due: float

  @classmethod
  def parse(cls, text: str) -> 'BpiStatementInfo':
    date_regex = f'{MONTH_REGEX}\s*(\d{{1,2}}),\s*(\d{{4}})'

    balances = re.compile(f'Previous\s*Balance (?P<balance>{AMOUNT_REGEX})').finditer(text)
    unbilled_installment = re.compile(f'Unbilled\s*Installment\s*Amount (?P<unbilled_installment>{AMOUNT_REGEX})').finditer(text)

    total_due = Currency.to_float(re.compile(f'TOTAL AMOUNT DUE ({AMOUNT_REGEX})').search(text).group(1))
    unbilled_installment = sum([Currency.to_float(match.group('unbilled_installment')) for match in unbilled_installment][1:])

    return cls(**{
      'customer_number': re.search(r'CUSTOMER NUMBER ([\d\-]+)', text).group(1),

      'statement_date': Date.to_datetime(re.compile(f'STATEMENT DATE ({date_regex})', flags=re.IGNORECASE).search(text).group(1)),
      'due_date': Date.to_datetime(re.compile(f'PAYMENT DUEDATE ({date_regex})', flags=re.IGNORECASE).search(text).group(1)),

      'credit_limit': Currency.to_float(re.compile(f'CREDIT LIMIT ({AMOUNT_REGEX})').search(text).group(1)),
      'total_due': total_due,
      'minimum_due': Currency.to_float(re.compile(f'MINIMUM AMOUNT DUE ({AMOUNT_REGEX})').search(text).group(1)),

      'previous_balance': sum([Currency.to_float(match.group('balance')) for match in balances]),
      'unbilled_installment': unbilled_installment,
      'outstanding_balance': total_due + unbilled_installment,
    })

class TransactionType(Enum):
  Payment = 'payment'
  Straight = 'straight'
  Refund = 'refund'
  Installment = 'installment'
  Amortization = 'amortization'

  @classmethod
  def get_type(cls, match: re.Match) -> 'TransactionType':
    if 'Thank You' in match.group('name'):
      return cls.Payment

    if match.group('sip_terms'):
      return cls.Installment

    if match.group('amortization'):
      return cls.Amortization
    
    if Currency.to_float(match.group('amount')) < 0:
      return cls.Refund

    return cls.Straight

class BpiTransaction(SimpleNamespace):
  type: TransactionType
  transaction_date: datetime
  posting_date: datetime

  description: str

  currency: str
  original_amount: float
  amount: float

  sip_terms: int
  amortization: int

  def to_json(self) -> dict:
    return {
      'type': self.type.value,
      'transaction_date': Date.to_text(self.transaction_date),
      'posting_date': Date.to_text(self.posting_date),
      'description': self.description,
      'currency': self.currency,
      'original_amount': self.original_amount,
      'amount': self.amount,
      'sip_terms': self.sip_terms,
      'amortization': self.amortization,
    }

  # param {year: Optional[int]} - statement year
  @classmethod
  def parse_multiple(cls, text: str, year: Optional[int] = None) -> List['BpiTransaction']:
    txn_regex = (
      f'(?P<txn_date>({MONTH_REGEX})\s*(\d{{1,2}}))\s+', # Transaction date
      f'(?P<posting_date>({MONTH_REGEX})\s*(\d{{1,2}}))\s+', # Posting date
      '(?P<name>.+?)', # Transaction name

      f'(\n(?P<currency>[A-Za-z\.]+)\s+(?P<original_amount>{AMOUNT_REGEX}))?', # Foreign currency
      f'(\s*{SIP_REGEX}?:\((?P<sip_terms>\d{{1,2}})Mos\.\))?', # SIP terms
      f'(\s*{SIP_REGEX}?:(?P<amortization>\d{{2}}\/\d{{2}}))?', # Amortization

      f'\s+(?P<amount>{AMOUNT_REGEX})' # Amount
    )

    date_format = '%B %d'

    matches = re.compile(''.join(txn_regex)).finditer(text)
    transactions = [
      {
        'type': TransactionType.get_type(match),
        'transaction_date': Date.to_datetime(match.group('txn_date'), format=date_format),
        'posting_date': Date.to_datetime(match.group('posting_date'), format=date_format),

        'description': match.group('name'),

        'currency': Currency.to_float(match.group('original_amount')),
        'original_amount': Currency.to_float(match.group('original_amount')),
        'amount': Currency.to_float(match.group('amount')),

        'sip_terms': match.group('sip_terms'),
        'amortization': match.group('amortization'),
      } for match in matches
    ]

    # If year is provided, we override the dates so we have more accurate dates
    if year:
      txn_months = [txn['transaction_date'].month for txn in transactions]
      has_dec_and_jan = 12 in txn_months and 1 in txn_months

      # Check if the statement has both transactions from December and January because we need to
      # determine if we need to use the previous year
      if has_dec_and_jan:
        return [
          cls(**{
            **txn,
            'transaction_date': txn['transaction_date'].replace(year=year - 1)
              if txn['transaction_date'].month == 12 else txn['transaction_date'].replace(year=year),
            'posting_date': txn['posting_date'].replace(year=year - 1)
              if txn['posting_date'].month == 12 else txn['posting_date'].replace(year=year),
          })
          for txn in transactions
        ]

      # If there are no rolling dates, we just use the year provided
      return [
        cls(**{
          **txn,
          'transaction_date': txn['transaction_date'].replace(year=year),
          'posting_date': txn['posting_date'].replace(year=year),
        })
        for txn in transactions
      ]

    return [cls(**txn) for txn in transactions]
