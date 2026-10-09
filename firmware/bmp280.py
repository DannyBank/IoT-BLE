# Minimal BMP280 driver (I2C addr 0x76 or 0x77), normal mode, x2 temp / x16 pressure, IIR filter 4.
import struct
import time


def compensate(cal, adc_t, adc_p):
    """Datasheet 3.11.3 integer compensation. Returns (temp_c, pressure_pa). Pure function."""
    T1, T2, T3, P1, P2, P3, P4, P5, P6, P7, P8, P9 = cal
    v1 = (((adc_t >> 3) - (T1 << 1)) * T2) >> 11
    v2 = (((((adc_t >> 4) - T1) * ((adc_t >> 4) - T1)) >> 12) * T3) >> 14
    t_fine = v1 + v2
    temp = ((t_fine * 5 + 128) >> 8) / 100.0

    v1 = t_fine - 128000
    v2 = v1 * v1 * P6
    v2 = v2 + ((v1 * P5) << 17)
    v2 = v2 + (P4 << 35)
    v1 = ((v1 * v1 * P3) >> 8) + ((v1 * P2) << 12)
    v1 = (((1 << 47) + v1) * P1) >> 33
    if v1 == 0:
        return temp, 0.0
    p = 1048576 - adc_p
    p = (((p << 31) - v2) * 3125) // v1
    v1 = (P9 * (p >> 13) * (p >> 13)) >> 25
    v2 = (P8 * p) >> 19
    p = ((p + v1 + v2) >> 8) + (P7 << 4)
    return temp, p / 256.0


class BMP280:
    def __init__(self, i2c, addr=None):
        self.i2c = i2c
        if addr is None:
            found = [a for a in (0x76, 0x77) if a in i2c.scan()]
            if not found:
                raise OSError('BMP280 not found on I2C')
            addr = found[0]
        self.addr = addr
        if i2c.readfrom_mem(addr, 0xD0, 1)[0] != 0x58:
            raise OSError('Unexpected BMP280 chip id')
        i2c.writeto_mem(addr, 0xE0, b'\xB6')            # soft reset
        time.sleep_ms(10)
        self.cal = struct.unpack('<HhhHhhhhhhhh', i2c.readfrom_mem(addr, 0x88, 24))
        i2c.writeto_mem(addr, 0xF5, b'\x10')            # filter x4, standby 0.5 ms
        i2c.writeto_mem(addr, 0xF4, b'\x57')            # T x2, P x16, normal mode
        time.sleep_ms(50)

    def read(self):
        """Returns (temp_c, pressure_hpa)."""
        d = self.i2c.readfrom_mem(self.addr, 0xF7, 6)
        adc_p = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4)
        adc_t = (d[3] << 12) | (d[4] << 4) | (d[5] >> 4)
        t, p = compensate(self.cal, adc_t, adc_p)
        return t, p / 100.0
