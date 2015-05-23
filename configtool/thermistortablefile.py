
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

  step = int((300.0 / (N-1) + 1))
  idx = range(step*(N-1), -step, -step)

  ofp.output("const uint16_t PROGMEM temptable[NUMTABLES][NUMTEMPS][2] = {")

  tcount = 0
  for tn in tl:
    tcount += 1
    finalTable = tcount == len(tl)
    if len(tn[0]) == 4:
      BetaTable(ofp, tn[0], tn[1], idx, settings, finalTable)
    elif len(tn[0]) == 7:
      SteinhartHartTable(ofp, tn[0], tn[1], idx, settings, finalTable)
    else:
      pass

  ofp.output("};")
  ofp.close()
  return True

def BetaTable(ofp, params, names, idx, settings, finalTable):
  r0 = params[0]
  beta = params[1]
  r2 = params[2]
  vadc = float(params[3])
  ofp.output("  // %s temp table using Beta algorithm with parameters:" %
             (", ".join(names)))
  ofp.output(("  // R0 = %s, T0 = %s, R1 = %s, R2 = %s, beta = %s, "
              "maxadc = %s") % (r0, settings.t0, settings.r1, r2,
              beta, settings.maxAdc))
  ofp.output("  {")

  thrm = BetaThermistor(int(r0), int(settings.t0), int(beta), int(settings.r1),
                        int(r2), vadc)

  for t in idx:
    a, r = thrm.setting(t)
    if a is None:
      ofp.output("// ERROR CALCULATING THERMISTOR VALUES AT TEMPERATURE %d" % t)
      continue

    vTherm = a * vadc / 1024
    ptherm = vTherm * vTherm / r
    if t <= 0:
      c = " "
    else:
      c = ","
    ostr = ("    {%4s, %5s}%s // %4d C, %6.0f ohms, %0.3f V,"
            " %0.2f mW") % (int(round(a)), t*4, c, t, r,
            vTherm, ptherm * 1000)
    ofp.output(ostr)

  if finalTable:
    ofp.output("  }")
  else:
    ofp.output("  },")

def SteinhartHartTable(ofp, params, names, idx, settings, finalTable):
  ofp.output(("  // %s temp table using Steinhart-Hart algorithm with "
              "parameters:") % (", ".join(names)))
  ofp.output(("  // Rp = %s, T0 = %s, R0 = %s, T1 = %s, R1 = %s, "
              "T2 = %s, R2 = %s") %
             (params[0], params[1], params[2], params[3], params[4], params[5],
              params[6]))
  ofp.output("  {")

  thrm = SHThermistor(int(params[0]), int(params[1]), int(params[2]),
                      int(params[3]), int(params[4]), int(params[5]),
                      int(params[6]))

  for t in idx:
    a, r = thrm.setting(t)
    if a is None:
      ofp.output("// ERROR CALCULATING THERMISTOR VALUES AT TEMPERATURE %d" % t)
      continue

    if t <= 0:
      c = " "
    else:
      c = ","
    ofp.output("    {%4d, %5d}%s // %4d C, %6.0f ohms, %7.2f adc" %
               (int(round(a)), t*4, c, t, int(round(r)), a))

  if finalTable:
    ofp.output("  }")
  else:
    ofp.output("  },")