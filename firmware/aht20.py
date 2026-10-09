# Minimal AHT20 driver (I2C addr 0x38) - non-blocking friendly: trigger() then read() >=80 ms later.
import time


class AHT20:
    ADDR = 0x38

    def __init__(self, i2c, addr=ADDR):
        self.i2c = i2c
        self.addr = addr
        time.sleep_ms(40)
        if not (self._status() & 0x08):          # not calibrated -> init
            self.i2c.writeto(self.addr, b'\xBE\x08\x00')
            time.sleep_ms(10)
            if not (self._status() & 0x08):
                raise OSError('AHT20 calibration failed')

    def _status(self):
        return self.i2c.readfrom(self.addr, 1)[0]

    def trigger(self):
        self.i2c.writeto(self.addr, b'\xAC\x33\x00')

    @staticmethod
    def _crc8(data):
        crc = 0xFF
        for b in data:
            crc ^= b
            for _ in range(8):
                crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
        return crc

    @staticmethod
    def convert(buf):
        """7 raw bytes -> (temp_c, humidity_pct). Pure function (unit-testable)."""
        raw_h = ((buf[1] << 12) | (buf[2] << 4) | (buf[3] >> 4))
        raw_t = (((buf[3] & 0x0F) << 16) | (buf[4] << 8) | buf[5])
        return raw_t * 200.0 / 1048576 - 50, raw_h * 100.0 / 1048576

    def read(self):
        """Call >= 80 ms after trigger(). Returns (temp_c, humidity_pct)."""
        buf = self.i2c.readfrom(self.addr, 7)
        if buf[0] & 0x80:
            raise OSError('AHT20 busy')
        if self._crc8(buf[:6]) != buf[6]:
            raise OSError('AHT20 CRC')
        return self.convert(buf)
