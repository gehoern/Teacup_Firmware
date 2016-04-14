
import os
from thermistor import SHThermistor, BetaThermistor


class ThermistorTableFile:
  def __init__(self, folder):
    self.error = False
    fn = os.path.join(folder, "thermistortable.h")
    try:
      self.fp = open(fn, 'wb')
    except:
      self.error = True

  def close(self):
    self.fp.close()

  def output(self, text):
    self.fp.write(text + "\n")

def paramsEqual(p1, p2):
  for i in range(len(p1)):
    if p1[i] != p2[i]:
      return False

  return True

def generateTempTables(sensors, settings):
  ofp = ThermistorTableFile(settings.folder)
  if ofp.error:
    return False

  N = int(settings.numTemps)

  tl = []
  for sensor in sensors:
    if sensor[3] is not None:
      found = False
      for t in tl:
        if paramsEqual(t[0], sensor[3]):
          t[1].append(sensor[0].upper())
          found = True
      if not found:
        tl.append((sensor[3], [sensor[0].upper()]))

  ofp.output("");
  ofp.output("/**");
  ofp.output("  This file was autogenerated when saving a board with");
  ofp.output("  Teacup's Configtool. You can edit it, but the next board");
  ofp.output("  save operation in Configtool will overwrite it without");
  ofp.output("  asking.");
  ofp.output("*/");
  ofp.output("");

  ofp.output("#define NUMTABLES %d" % len(tl))
  ofp.output("#define NUMTEMPS %d" % N)
  ofp.output("");

  for i in range(len(tl)):
    for n in tl[i][1]:
      ofp.output("#define THERMISTOR_%s %d" % (n, i))
  ofp.output("");

  if len(tl) == 0 or N == 0:
    ofp.close();
    return True

  ofp.output("const uint16_t PROGMEM temptable[NUMTABLES][NUMTEMPS][2] = {")

  tcount = 0
  for tn in tl:
    tcount += 1
    finalTable = tcount == len(tl)
    if len(tn[0]) == 4:
      BetaTable(ofp, tn[0], tn[1], settings, finalTable)
    elif len(tn[0]) == 7:
      SteinhartHartTable(ofp, tn[0], tn[1], settings, finalTable)
    else:
      pass

  ofp.output("};")
  ofp.close()
  return True

def BetaTable(ofp, params, names, settings, finalTable):
  r0 = params[0]
  beta = params[1]
  r2 = params[2]
  vadc = float(params[3])
  maxAdc = int(settings.maxAdc)
  ofp.output("  // %s temp table using Beta algorithm with parameters:" %
             (", ".join(names)))
  ofp.output(("  // R0 = %s, T0 = %s, R1 = %s, R2 = %s, beta = %s, "
              "maxadc = %s") % (r0, settings.t0, settings.r1, r2,
              beta, maxAdc))
  ofp.output("  {")

  thrm = BetaThermistor(int(r0), int(settings.t0), int(beta), int(settings.r1),
                        int(r2), vadc, maxAdc=maxAdc)

  hiadc = thrm.setting(0)[0]
  N = int(settings.numTemps)

  samples = optimizeTempTable(thrm, N, hiadc)

  for i in samples:
    t = thrm.temp(i)
    if t is None:
      ofp.output("// ERROR CALCULATING THERMISTOR VALUES AT ADC %d" % i)
      continue

    v = thrm.adcInv(i)
    r = thrm.resistance(t)

    vTherm = i * vadc / (maxAdc + 1)
    ptherm = vTherm * vTherm / r
    if i == max(samples):
      c = " "
    else:
      c = ","
    ostr = ("    {%4s, %5s}%s // %4d C, %6.0f ohms, %0.3f V,"
            " %0.2f mW") % (i, int(t * 4), c, int(t), int(round(r)),
            vTherm, ptherm * 1000)
    ofp.output(ostr)

  if finalTable:
    ofp.output("  }")
  else:
    ofp.output("  },")

def SteinhartHartTable(ofp, params, names, settings, finalTable):
  maxAdc = int(settings.maxAdc)
  ofp.output(("  // %s temp table using Steinhart-Hart algorithm with "
              "parameters:") % (", ".join(names)))
  ofp.output(("  // Rp = %s, T0 = %s, R0 = %s, T1 = %s, R1 = %s, "
              "T2 = %s, R2 = %s, maxadc = %s") %
             (params[0], params[1], params[2], params[3], params[4], params[5],
              params[6], maxAdc))
  ofp.output("  {")

  thrm = SHThermistor(int(params[0]), float(params[1]), int(params[2]),
                      float(params[3]), int(params[4]), float(params[5]),
                      int(params[6]), maxAdc=maxAdc)

  hiadc = thrm.setting(0)[0]
  N = int(settings.numTemps)

  samples = optimizeTempTable(thrm, N, hiadc)

  for i in samples:
    t = thrm.temp(i)
    if t is None:
      ofp.output("// ERROR CALCULATING THERMISTOR VALUES AT ADC %d" % i)
      continue

    r = int(thrm.adcInv(i))

    if i == max(samples):
      c = " "
    else:
      c = ","
    ofp.output("    {%4d, %5d}%s // %4d C, %6d ohms" %
               (i, int(t * 4), c, int(t), int(round(r))))

  if finalTable:
    ofp.output("  }")
  else:
    ofp.output("  },")

def optimizeTempTable(thrm, length, hiadc):

  # This is a variation of the Ramer-Douglas-Peucker algorithm, see
  # https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm
  #
  # It works like this:
  #
  #   - Calculate all (1024) ideal values.
  #   - Keep only the ones in the interesting range (0..500C).
  #   - Insert the two extremes into our sample list.
  #   - Calculate the linear approximation of the remaining values.
  #   - Insert the correct value for the "most-wrong" estimation into our
  #     sample list.
  #   - Repeat until "N" values are chosen as requested.

  # Calculate actual temps for all ADC values.
  actual = dict([(x, thrm.temp(1.0 * x)) for x in range(1, int(hiadc + 1))])

  # Limit ADC range to 0C to 500C.
  MIN_TEMP = 0
  MAX_TEMP = 500
  actual = dict([(adc, actual[adc]) for adc in actual
                 if actual[adc] <= MAX_TEMP and actual[adc] >= MIN_TEMP])

  # Build a lookup table starting with the extremes.
  A = min(actual)
  B = max(actual)
  lookup = dict([(x, actual[x]) for x in [A, B]])
  error = dict({})
  while len(lookup) < length:
    error.update(dict([(x, abs(actual[x] - LinearTableEstimate(lookup, x)))
                       for x in range(A + 1, B)]))

    # Correct the most-wrong lookup value.
    next = max(error, key = error.get)
    lookup[next] = actual[next]

    # Prepare to update the error range.
    A = before(lookup, next)
    B = after(lookup, next)

  return sorted(lookup)

def after(lookup, value):
  return min([x for x in lookup.keys() if x > value])

def before(lookup, value):
  return max([x for x in lookup.keys() if x < value])

def LinearTableEstimate(lookup, value):
  if value in lookup:
    return lookup[value]

  # Estimate result with linear estimation algorithm.
  x0 = before(lookup, value)
  x1 = after(lookup, value)
  y0 = lookup[x0]
  y1 = lookup[x1]
  return ((value - x0) * y1 + (x1 - value) * y0) / (x1 - x0)
