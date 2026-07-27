"""Cálculo de retrocesos y extensiones de Fibonacci."""
from typing import Dict


class FibonacciCalculator:
    LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    EXTENSIONS = [1.0, 1.272, 1.618, 2.0, 2.618]

    @staticmethod
    def get_retracements(wave_end: float, wave_start: float) -> Dict[float, float]:
        """
        0% = wave_end (el extremo recién alcanzado, sin retroceso todavía)
        100% = wave_start (retroceso completo hasta el origen de la onda)
        Funciona igual para ondas alcistas y bajistas: el signo de la resta
        ya captura la dirección, no hace falta un parámetro 'trend' aparte.
        """
        diff = wave_end - wave_start
        return {level: wave_end - diff * level for level in FibonacciCalculator.LEVELS}

    @staticmethod
    def get_extensions(wave1_start, wave1_end, wave2_end) -> Dict[float, float]:
        w1_size = abs(wave1_end - wave1_start)
        if wave1_end > wave1_start:
            return {ext: wave2_end + w1_size * ext for ext in FibonacciCalculator.EXTENSIONS}
        else:
            return {ext: wave2_end - w1_size * ext for ext in FibonacciCalculator.EXTENSIONS}
