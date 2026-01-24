import re


def safe_eval(expression):
    """Safely evaluate mathematical expressions"""
    try:
        expression = expression.strip()
        if not expression:
            return 0
        if not re.match(r'^[\d+\-*/().\s]+$', expression):
            return None
        result = eval(expression, {"__builtins__": {}}, {})
        return float(result)
    except:
        return None


def armor_to_reduction(armor):
    """Convert armor value to physical reduction percentage"""
    return (0.06 * armor) / (1 + 0.06 * armor) * 100


def reduction_to_armor(reduction):
    """Convert reduction percentage to armor value"""
    if reduction >= 100:
        return 999
    return reduction / (0.06 * (100 - reduction))


def has_operators(s):
    """Check if string contains math operators"""
    return any(op in s for op in ['+', '*', '/']) or \
           (s.count('-') > 1 or (s.count('-') == 1 and not s.strip().startswith('-')))


def is_expression(s):
    """Check if string contains operators (is an expression)"""
    return any(op in s for op in ['+', '-', '*', '/']) and not s.strip().startswith('-')


def eval_armor_expression(expr_str):
    """
    Evaluate armor expression with special handling:
    - Addition/subtraction: operate on armor values
    - Multiplication/division: operate on reduction values
    Returns (reduction_value, display_armor_value)
    """
    expr_str = expr_str.strip()
    if not expr_str:
        return 0, 0

    # Check if it's a simple number
    try:
        armor = float(expr_str)
        return armor_to_reduction(armor), armor
    except ValueError:
        pass

    # Check for multiplication/division at the END of expression
    mult_match = re.match(r'^(.+)\*\s*([\d.]+)$', expr_str)
    if mult_match:
        left_expr = mult_match.group(1).strip()
        multiplier = float(mult_match.group(2))
        left_armor = safe_eval(left_expr)
        if left_armor is not None:
            base_reduction = armor_to_reduction(left_armor)
            final_reduction = base_reduction * multiplier
            return final_reduction, None

    div_match = re.match(r'^(.+)/\s*([\d.]+)$', expr_str)
    if div_match:
        left_expr = div_match.group(1).strip()
        divisor = float(div_match.group(2))
        if divisor != 0:
            left_armor = safe_eval(left_expr)
            if left_armor is not None:
                base_reduction = armor_to_reduction(left_armor)
                final_reduction = base_reduction / divisor
                return final_reduction, None

    # For addition/subtraction or other expressions, evaluate as armor
    result = safe_eval(expr_str)
    if result is not None:
        return armor_to_reduction(result), result

    return 0, 0


def eval_reduction_expression(expr_str):
    """Evaluate reduction expression (simple eval)"""
    result = safe_eval(expr_str)
    return result if result is not None else 0
