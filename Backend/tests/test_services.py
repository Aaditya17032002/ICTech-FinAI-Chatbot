import pytest

from app.utils.calculations import (
    calculate_cagr,
    calculate_absolute_return,
    format_indian_currency,
    format_percentage,
)


class TestCalculations:
    """Tests for financial calculations."""
    
    def test_cagr_positive_growth(self):
        """Test CAGR calculation with positive growth."""
        cagr = calculate_cagr(100, 150, 3)
        assert cagr is not None
        assert 14 < cagr < 15
    
    def test_cagr_negative_growth(self):
        """Test CAGR calculation with negative growth."""
        cagr = calculate_cagr(100, 80, 2)
        assert cagr is not None
        assert cagr < 0
    
    def test_cagr_invalid_inputs(self):
        """Test CAGR with invalid inputs."""
        assert calculate_cagr(0, 100, 3) is None
        assert calculate_cagr(100, 0, 3) is None
        assert calculate_cagr(100, 150, 0) is None
        assert calculate_cagr(-100, 150, 3) is None
    
    def test_absolute_return(self):
        """Test absolute return calculation."""
        result = calculate_absolute_return(100, 150)
        assert result == 50.0
    
    def test_absolute_return_negative(self):
        """Test absolute return with loss."""
        result = calculate_absolute_return(100, 80)
        assert result == -20.0
    
    def test_absolute_return_invalid(self):
        """Test absolute return with invalid input."""
        assert calculate_absolute_return(0, 100) is None
        assert calculate_absolute_return(-100, 50) is None
    
    def test_format_indian_currency_crores(self):
        """Test formatting large amounts in crores."""
        result = format_indian_currency(50_000_000)
        assert "Cr" in result
        assert "5.00" in result
    
    def test_format_indian_currency_lakhs(self):
        """Test formatting amounts in lakhs."""
        result = format_indian_currency(500_000)
        assert "L" in result
        assert "5.00" in result
    
    def test_format_indian_currency_thousands(self):
        """Test formatting amounts in thousands."""
        result = format_indian_currency(5_000)
        assert "K" in result
        assert "5.00" in result
    
    def test_format_indian_currency_small(self):
        """Test formatting small amounts."""
        result = format_indian_currency(500)
        assert "₹500.00" == result
    
    def test_format_percentage(self):
        """Test percentage formatting."""
        assert format_percentage(15.5) == "15.50%"
        assert format_percentage(15.567, 1) == "15.6%"
        assert format_percentage(-5.5) == "-5.50%"
