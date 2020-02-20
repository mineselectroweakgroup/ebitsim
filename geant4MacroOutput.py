from commonUtils import getElementAbv
import math


def geant4MacroOutput(species, ebitParams, outputConfig):
    print("Hello! We're the GEANT4 macro output interface!\n")

    # Open the macro file for writing, we should overwrite for now..
    with open(outputConfig.outputFileName, 'w') as geantMacroFile:

        for mySpecies in species:
            mySpeciesName = getElementAbv(mySpecies.Z)
            for chargeStateResults in range(0, len(mySpecies.results)):
                # mylabel = getElementAbv(mySpecies.Z)

                print("Element : %s, Z: %i, A: %i, Q: %i" % (mySpeciesName, mySpecies.Z, mySpecies.A, mySpecies.chargeStates[chargeStateResults]))
                print("Total Simulated Time : %f" % (ebitParams.breedingTime))
                stepSize = (math.floor(len(mySpecies.results[chargeStateResults]) / outputConfig.subDivisionOfTime))
                for myrow in range(0, len(mySpecies.results[chargeStateResults]), stepSize):
                    if mySpecies.results[chargeStateResults][myrow][1] != 0:
                        print("MyRow : %i, Row 0: %f, Row 1: %f" % (myrow, mySpecies.results[chargeStateResults][myrow][0], mySpecies.results[chargeStateResults][myrow][1]))
                        # Write header before each line of beam run macro info so we can split this up easily later
                        geantMacroFile.write("# START: E:%s,Z:%i,A:%i,Q:%i:T:%f\n" % (mySpeciesName,
                                                                                      mySpecies.Z,
                                                                                      mySpecies.A,
                                                                                      mySpecies.chargeStates[chargeStateResults],
                                                                                      mySpecies.results[chargeStateResults][myrow][0]))
                        geantMacroFile.write("/pga/selectGunAction 1\n")
                        geantMacroFile.write("/gps/particle ion\n")
                        geantMacroFile.write("/gps/ion %i %i %i\n" % (mySpecies.Z,  mySpecies.A, mySpecies.chargeStates[chargeStateResults]))  # /gps/ion Z, A, Q, E
                        geantMacroFile.write("/gps/position 0 0 0\n")
                        geantMacroFile.write("/gps/ene/mono 0\n")
                        geantMacroFile.write("/histo/filename E:%s,Z:%i,A:%i,Q:%i:T:%f\n" % (mySpeciesName,
                                                                                             mySpecies.Z,
                                                                                             mySpecies.A,
                                                                                             mySpecies.chargeStates[chargeStateResults],
                                                                                             mySpecies.results[chargeStateResults][myrow][0]))
                        geantMacroFile.write("/run/beamOn %i\n" % (outputConfig.eventsPerTimeSlice * mySpecies.results[chargeStateResults][myrow][1]))
                        geantMacroFile.write("# END\n")
                        # geantMacroFile.write("")
    return 0
