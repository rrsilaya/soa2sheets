from soa2sheets.lib.bpi.parser import BpiStatementInfo, BpiTransaction
from soa2sheets.lib.bpi.utils import Date

from flask import Request, jsonify
from pypdf import PdfReader

def parse_soa(request: Request):
  if request.method != 'POST':
    return jsonify({ 'error': 'Method not allowed' }), 405

  file = request.files['file']
  if not file:
    return jsonify({ 'error': 'No file uploaded' }), 400

  pdf = PdfReader(file)
  text = ''.join([page.extract_text() for page in pdf.pages])

  statement_info = BpiStatementInfo.parse(text)
  transactions = BpiTransaction.parse_multiple(text, year=statement_info.statement_date.year)

  return jsonify({
    'status': 'success',
    'account_info': {
      'customer_number': statement_info.customer_number,
      'credit_limit': statement_info.credit_limit,
    },
    'statement': {
      'statement_date': Date.to_text(statement_info.statement_date),
      'due_date': Date.to_text(statement_info.due_date),
      'total_due': statement_info.total_due,
      'minimum_due': statement_info.minimum_due,
    },
    'transactions': [transaction.to_json() for transaction in transactions],
  })
