#!/usr/bin/env python
from math import *
from IonizationEnergies import *
from rr import *
import copy

__EMASS__ = 5.11e5  # "Electron mass in eV"
__C__ = 3.0e10  # "Speed of light"
__ECHG__ = 1.6e-19  # "Electron charge"
__VBOHR__ = 2.2e8
__AMU__ = 9.311e8  # "1 AMU in eV"
__TORR__ = 3.537e16  # "1 torr in cm-3"
__ALPHA__ = 7.2974e-3  # "fine-structure constant"
__CHEXCONST__ = 2.25e-16  # "Constant for use in charge-exchange "
__LCONV__ = 3.861e-11  # "length conversion factor to CGS"

__MAXCHARGE__ = 105
__MAXSPECIES__ = 1000
INITILIZEDEVERYTHING = 0

class Species:
    def __init__(self,
                 Z,
                 A,
                 decaysTo=0.0,
                 betaHalfLife=0.0,
                 initSCIPop=1.0,
                 chargeStates=None,
                 population=None,
                 decayConstant=0.0,
                 ionizationRates=None,
                 rrRates=None,
                 chargeExchangeRates=None,
                 k1=[],
                 k2=[],
                 k3=[],
                 k4=[],
                 tmpPop=[],
                 y1=[],
                 y12=[],
                 y22=[],
                 results=[]):
        self.Z = Z
        self.A = A
        self.decaysTo = decaysTo
        self.betaHalfLife = betaHalfLife
        self.initSCIPop = initSCIPop
        self.decayConstant = decayConstant
        self.chargeStates = chargeStates
        self.results = results

# I think I need to move chargeStates up to here.. could concievibly do that for a bunch
# of the stuff in chargepopparams due to maybe they should be following the species around


class RkStepParams:
    def __init__(self, minCharge=5e-5, tStep=1e-6, desiredAccuracyPerChargeState=1e-7, desiredAccuracy=0):
        self.minCharge = minCharge
        self.tStep = tStep
        self.desiredAccuracyPerChargeState = desiredAccuracyPerChargeState
        self.desiredAccuracy = desiredAccuracy

class EbitParams:
    def __init__(self,
                 breedingTime=0.1,
                 probeEvery=0.1,
                 ionEbeamOverlap=1.0,
                 beamEnergy=3000.0,
                 beamCurrent=0.1,
                 beamRadius=200.0e-4,
                 pressure=1e-12,
                 ionTemperature=100.0,
                 ignoreBetaDecay=1,
                 currentDensity=None,
                 rkParams=None,
                 decayConstants=[]):  # I'm throwing decay constants in here so I can have those ready for the beta decay stuff without having to pass all the species objects
        self.breedingTime = breedingTime
        self.probeEvery = probeEvery
        self.ionEbeamOverlap = ionEbeamOverlap
        self.beamEnergy = beamEnergy
        self.beamCurrent = beamCurrent
        self.beamRadius = beamRadius
        self.pressure = pressure
        self.ionTemperature = ionTemperature
        self.currentDensity = currentDensity
        self.rkParams = rkParams
        self.decayConstants = decayConstants
        self.ignoreBetaDecay = ignoreBetaDecay


def createEmptyList(sizeOfArray):
    myEmptyList = [0.0 for i in range(sizeOfArray)]
    return myEmptyList


def createDecayConstants(betaHalfLife):
    if betaHalfLife <= 0:
        decayConstant = 0.0
    else:
        decayConstant = log(2) / betaHalfLife
    return decayConstant


def createChargeExchangeRates(Z, A, pressure, ionTemperature):
    chargeExchangeRates = [0] * (Z + 1)

    # Need to return a Z+1 array
    h2Density = pressure * __TORR__
    ionMassInAMU = A * __AMU__
    avgIonV = __C__ * sqrt(8.0 * (ionTemperature / (pi * ionMassInAMU)))
    avgIonVinBohr = avgIonV / __VBOHR__
    sigV = __CHEXCONST__ * log( 15.0 / avgIonVinBohr) * avgIonV

    for i in range(1, Z + 1):
        chargeExchangeRates[i] = i * sigV * h2Density
    return chargeExchangeRates


def createInteractionRates(Z, beamEnergy, currentDensity, crossSections):
    # From Lisp Code :
    #  "Calculate the rate for a specific interaction (ionization/rr/..)
    #  inside the trap given the BEAM-ENERGY in eV, CURRENT-DENSITY in
    #  A/cm2, and the CROSS-SECTIONS in cm-2 corresponding to the
    #  interaction. Returns array of size Z-ION+1 with rates."
    interactionRate = [0] * (Z + 1)

    electronVelocity = __C__ * sqrt(2 * (beamEnergy / __EMASS__))
    electronRate = currentDensity / __ECHG__ / electronVelocity

    for i in range(0, Z + 1):
        interactionRate[i] = crossSections[i] * electronVelocity * electronRate

    return interactionRate


def createDefaultInteractionRates(myspecies, ebitparams, probeFnAddPop, runChargeExchange=0):  # move away from chex=0 and move into object

    interactionRates = createEmptyList(myspecies.Z + 2)
    if runChargeExchange == 0:
        myFuncValues = createInteractionRates(myspecies.Z, ebitparams.beamEnergy, ebitparams.currentDensity, probeFnAddPop(ebitparams.beamEnergy, myspecies.Z))
    else:
        myFuncValues = probeFnAddPop(myspecies.Z, myspecies.A, ebitparams.pressure, ebitparams.ionTemperature)

    for r in range(0, len(myFuncValues)):
        interactionRates[r] = myFuncValues[r]
    return interactionRates


def betaDecay(myspecies, species, ebitparams, zindex, tstep):
    mySpeciesIndex = species.index(myspecies)
    if zindex >= 1:
        try:
            myval = ((-1 * ebitparams.decayConstants[mySpeciesIndex] * myspecies.tmpPop[zindex])
                     + (ebitparams.decayConstants[mySpeciesIndex + 1] * species[mySpeciesIndex + 1].tmpPop[zindex]))
        except IndexError:   # *** PLEASE MAKE SURE THIS IS A DECENT ASSUMPTION OF WHAT I SHOULD DO... TEST ME! ***
            myval = (-1 * ebitparams.decayConstants[mySpeciesIndex] * myspecies.tmpPop[zindex])
    else:
        myval = 0
    return tstep * myval


def calculateK(ebitparams, myspecies, species, tmpPop, Z, ionizationRates, chargeExchangeRates, rrRates,  retK, p1, p2, addWFactor, tstep):
    betaDecayDelta = 0
    nonDecayLastDelta = 0.0

    for zindex in range(0, Z):
        tmpPop[zindex] = p1[zindex] + (p2[zindex] * addWFactor)

    for zindex in range(0, Z):  # at some point eval if you need both these loops...
        # Used to use chargeChanges but it was a little faster having this inline
        nonDecayDelta = tstep * ((-1 * ionizationRates[zindex] * tmpPop[zindex])
                                 + ((chargeExchangeRates[zindex + 1] + rrRates[zindex + 1]) * tmpPop[zindex + 1]))

        if ebitparams.ignoreBetaDecay != 1:  # ignore if we don't have any to speed things up
            betaDecayDelta = betaDecay(myspecies, species, ebitparams, zindex, tstep)

        retK[zindex] = (nonDecayDelta - nonDecayLastDelta) + betaDecayDelta
        nonDecayLastDelta = nonDecayDelta
        retK[Z] = (-nonDecayLastDelta) + betaDecayDelta

    return retK


def rkStep(ebitparams, myspecies, species, tstep, populationAtT0, populationAtTtstep):
    # longer function param calls yes but it speeds it up calculateK by 10%...
    myspecies.k1 = calculateK(ebitparams, myspecies, species, myspecies.tmpPop, myspecies.Z, myspecies.ionizationRates, myspecies.chargeExchangeRates, myspecies.rrRates, myspecies.k1, populationAtT0, myspecies.tmpPop, 0.0, tstep)
    myspecies.k2 = calculateK(ebitparams, myspecies, species, myspecies.tmpPop, myspecies.Z, myspecies.ionizationRates, myspecies.chargeExchangeRates, myspecies.rrRates, myspecies.k2, populationAtT0, myspecies.k1, 0.5, tstep)
    myspecies.k3 = calculateK(ebitparams, myspecies, species, myspecies.tmpPop, myspecies.Z, myspecies.ionizationRates, myspecies.chargeExchangeRates, myspecies.rrRates, myspecies.k3, populationAtT0, myspecies.k2, 0.5, tstep)
    myspecies.k4 = calculateK(ebitparams, myspecies, species, myspecies.tmpPop, myspecies.Z, myspecies.ionizationRates, myspecies.chargeExchangeRates, myspecies.rrRates, myspecies.k4, populationAtT0, myspecies.k3, 1.0, tstep)

    for zindex in range(0, myspecies.Z):
        populationAtTtstep[zindex] = populationAtT0[zindex] + ((1 / 6) * (myspecies.k1[zindex] + (2 * (myspecies.k2[zindex] + myspecies.k3[zindex])) + myspecies.k4[zindex]))
    return


def probeFnAddPop(time, ebitparams, myspecies):
    #  In the original lisp code this function was passed along to calcChargePopulations
    #  so for now I will do the same as apparently this is something someone might want
    #  to change to a different function... If someone knows the reason for this please
    #  let me know.
    for chargeIndex in range(0, len(myspecies.chargeStates)):
        if len(myspecies.results) < len(myspecies.chargeStates):
            myspecies.results.append([])
        myspecies.results[chargeIndex].append([time, myspecies.population[myspecies.chargeStates[chargeIndex]]])


def adaptiveRkStepper(species, ebitparams, probeFnAddPop):
    for myspecies in species:
        time = 0.0
        nextPrint = 0.0
        noTooBigSteps = 0
        step = ebitparams.rkParams.tStep
        bestStepSize = step
        print("Simulating Species : %s" % myspecies.Z)

        while time <= ebitparams.breedingTime:
            if time >= nextPrint:
                nextPrint = nextPrint + ebitparams.probeEvery
                probeFnAddPop(time, ebitparams, myspecies)

            rkStep(ebitparams, myspecies, species, 2 * step, myspecies.population, myspecies.y1)
            rkStep(ebitparams, myspecies, species, step, myspecies.population, myspecies.y12)
            rkStep(ebitparams, myspecies, species, step, myspecies.y12, myspecies.y22)

            diff = sum([abs(x - y) for (x, y) in zip(myspecies.y1, myspecies.y22)])  # This just takes a differences and sums all the diffs

            if diff > 0:
                bestStepSize = step * ((ebitparams.rkParams.desiredAccuracy / diff) ** 0.2)
            else:
                time = time + step
                myspecies.population = copy.copy(myspecies.y22)
                continue  # if we got here then we can skip to the top of the while statement
            if bestStepSize >= step:
                time = time + step
                myspecies.population = copy.copy(myspecies.y22)
            else:
                noTooBigSteps = noTooBigSteps + 1

            step = 0.9 * bestStepSize
        # print(myspecies.results)
    return

def initEverything(species, ebitparams):
    global INITILIZEDEVERYTHING

    ebitparams.rkParams = RkStepParams()

    ebitparams.rkParams.desiredAccuracy = ebitparams.rkParams.desiredAccuracyPerChargeState / species[0].Z

    ebitparams.currentDensity = (ebitparams.ionEbeamOverlap * ebitparams.beamCurrent) / (pi * (ebitparams.beamRadius ** 2))

    species.sort(key=lambda x: x.Z, reverse=True)  # Sort species list by Z in decending order
    largestZValue = species[0].Z  # We need the largest value for the size of the population array

    if species[0].betaHalfLife != 0.0:  # The largest Z value species is not allowed to have a beta decay
        raise ValueError("Can not handle having a beta decay for highest Z species")

    for myspecies in species:
        # Initilize everything ...
        myspecies.population = createEmptyList(largestZValue + 2)
        myspecies.population[1] = myspecies.initSCIPop
        myspecies.decayConstant = createDecayConstants(myspecies.betaHalfLife)

        if myspecies.decayConstant > 0:  # If we don't need it we will use this to ignore the beta calculation function
            ebitparams.ignoreBetaDecay = 0

        ebitparams.decayConstants.append(myspecies.decayConstant)
        myspecies.ionizationRates = createDefaultInteractionRates(myspecies, ebitparams, createIonizationCrossSections)
        myspecies.rrRates = createDefaultInteractionRates(myspecies, ebitparams, createRRCrossSections)
        myspecies.chargeExchangeRates = createDefaultInteractionRates(myspecies, ebitparams, createChargeExchangeRates, 1)
        myspecies.k1 = createEmptyList(species[0].Z + 2)
        myspecies.k2 = createEmptyList(species[0].Z + 2)
        myspecies.k3 = createEmptyList(species[0].Z + 2)
        myspecies.k4 = createEmptyList(species[0].Z + 2)
        myspecies.tmpPop = createEmptyList(species[0].Z + 2)
        myspecies.y1 = createEmptyList(species[0].Z + 2)
        myspecies.y12 = createEmptyList(species[0].Z + 2)
        myspecies.y22 = createEmptyList(species[0].Z + 2)
        myspecies.results = []
    INITILIZEDEVERYTHING = 1


def calcChargePopulations(species, ebitparams, probeFnAddPop):
    if INITILIZEDEVERYTHING == 0:
        initEverything(species, ebitparams)

    adaptiveRkStepper(species, ebitparams, probeFnAddPop)  # this does all the heavy lifting

    return


#def main():
#    chargeStates = [39, 40, 41, 42, 43]

#    species = []

    # rewrite a bunch of this....
#    species.append(Species(51, 129, 0.0, 0.0, 1.0, chargeStates))
  #  species.append(Species(22, 122, 0.0, 0.01, 1.0, chargeStates))
  #  species.append(Species(54, 123, 0.0, 0.0, 1.0, chargeStates))
  #  species.append(Species(4, 107, 0.0, 0.0, 7.0, chargeStates))
 #   species.append(Species(2, 107, 0.0, 1.0, 6.0, chargeStates))
 #   species.append(Species(6, 107, 0.0, 0.0, 5.0, chargeStates))
#    species.append(Species(2, 107, 0.0, 1.0, 6.0))
#    species.append(Species(6, 107, 0.0, 0.0, 5.0))
#    ebitparams = EbitParams(breedingTime=11.0, beamEnergy=7000.0, pressure=1e-10, beamCurrent=0.02, beamRadius=90e-4, probeEvery=1.0)

#    calcChargePopulations(species, ebitparams, probeFnAddPop)
#    return 0

#main()