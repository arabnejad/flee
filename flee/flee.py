import random
import numpy as np
import csv
import sys
import copy
from flee.SimulationSettings import SimulationSettings
from flee.Diagnostics import write_agents


class Person:
    """
    The base class for the agent object

    Attributes:
        distance_moved_this_timestep (float): Description
        distance_travelled (int): Description
        distance_travelled_on_link (int): Description
        home_location (TYPE): Description
        location (TYPE): Description
        places_travelled (int): Description
        recent_travel_distance (float): Description
        timesteps_since_departure (int): Description
        travelling (bool): Description

    """

    __slots__ = ["location", "distance_travelled", "home_location",
                 "timesteps_since_departure", "places_travelled",
                 "recent_travel_distance", "distance_moved_this_timestep",
                 "travelling", "distance_travelled_on_link"]

    def __init__(self, location):
        self.location = location
        self.home_location = location
        self.location.IncrementNumAgents()
        self.timesteps_since_departure = 0
        self.places_travelled = 1

        # An index of how much the agent has recently travelled (range
        # 0.0-1.0).
        self.recent_travel_distance = 0.0
        # Number of km moved this timestep.
        self.distance_moved_this_timestep = 0.0

        # Set to true when an agent resides on a link.
        self.travelling = False

        # Tracks how much distance a Person has been able to travel on the
        # current link.
        self.distance_travelled_on_link = 0

        # if not SimulationSettings.TurnBackAllowed:
        #  self.last_location = None

        if SimulationSettings.AgentLogLevel > 0:
            self.distance_travelled = 0

    def evolve(self, ForceTownMove=False):
        """
        This should be completed !!!

        Args:
            ForceTownMove (bool, optional): Description
        """

        if self.travelling is False:
            if self.location.town and ForceTownMove:
                movechance = 1.0
            else:
                movechance = self.location.movechance

            outcome = random.random()
            # print(movechance)

            if outcome < movechance:
                # determine here which route to take?
                if SimulationSettings.UseV1Rules:
                    chosenRoute = self.selectRouteRuleset1()
                else:
                    chosenRoute = self.selectRouteRuleset2()

                # if there is a viable route to a different location.
                if chosenRoute >= 0:
                    # update location to link endpoint
                    self.location.DecrementNumAgents()
                    self.location = self.location.links[chosenRoute]
                    self.location.IncrementNumAgents()
                    self.travelling = True
                    self.distance_travelled_on_link = 0

    def finish_travel(self):
        """
        checks if the agent
        """
        if self.travelling:

            if self.places_travelled == 1 and SimulationSettings.StartOnFoot:
                # First journey
                self.distance_travelled_on_link += SimulationSettings.MaxWalkSpeed
                self.distance_moved_this_timestep += SimulationSettings.MaxWalkSpeed
            else:
                self.distance_travelled_on_link += SimulationSettings.MaxMoveSpeed
                self.distance_moved_this_timestep += SimulationSettings.MaxMoveSpeed

            # If destination has been reached.
            if self.distance_travelled_on_link > self.location.distance:

                self.places_travelled += 1
                # remove the excess km tracked by the
                # distance_moved_this_timestep var.
                self.distance_moved_this_timestep += self.location.distance - \
                    self.distance_travelled_on_link

                # update agent logs
                if SimulationSettings.AgentLogLevel > 0:
                    self.distance_travelled += self.location.distance

                # if link is closed, bring agent to start point instead of the
                # destination and return.
                if self.location.closed is True:
                    self.location.DecrementNumAgents()
                    self.location = self.location.startpoint
                    self.location.IncrementNumAgents()
                    self.travelling = False
                    self.distance_travelled_on_link = 0

                else:
                    # if the person has moved less than the minMoveSpeed, it
                    # should go through another evolve() step in the new
                    # location.
                    evolveMore = False
                    if (self.distance_moved_this_timestep <
                            SimulationSettings.MaxMoveSpeed):
                        evolveMore = True

                    # update location (which is on a link) to link endpoint
                    self.location.DecrementNumAgents()
                    self.location = self.location.endpoint
                    self.location.IncrementNumAgents()

                    self.travelling = False
                    self.distance_travelled_on_link = 0

                    if SimulationSettings.CampLogLevel > 0:
                        if self.location.Camp is True:
                            self.location.incoming_journey_lengths += [
                                self.timesteps_since_departure]

                    # Perform another evolve step if needed. And if it results
                    # in travel, then the current travelled distance needs to
                    # be taken into account.
                    if evolveMore is True:
                        ForceTownMove = False
                        if SimulationSettings.AvoidShortStints:
                            # Flee 2.0 Changeset 1, factor 2.
                            if (
                                self.recent_travel_distance +
                                    (self.distance_moved_this_timestep /
                                        SimulationSettings.MaxMoveSpeed
                                     )
                            ) / 2.0 < 0.5:
                                ForceTownMove = True

                        self.evolve(ForceTownMove)
                        self.finish_travel()

    def getLinkWeight(self, link, awareness_level):
        """
        Calculate the weight of an adjacent link. Weight = probability
        that it will be chosen.

        Args:
            link (Link obj): Description
            awareness_level (int): Description

        Returns:
            TYPE: Description
        """

        # If turning back is NOT allowed, remove weight from the last location.
        # if not SimulationSettings.TurnBackAllowed:
        #  if link.endpoint == self.last_location:
        # return 0.0 #float(0.1 / float(SimulationSettings.Softening +
        # link.distance))

        if awareness_level < 0:
            return 1.0

        return float(link.endpoint.scores[awareness_level] /
                     float(SimulationSettings.Softening + link.distance)
                     )

    def normalizeWeights(self, weights):
        """
        Normalized the weight values

        Args:
            weights (TYPE): Description

        Returns:
            TYPE: Description
        """
        if np.sum(weights) > 0.0:
            weights /= np.sum(weights)
        else:  # if all have zero weight, then we do equal weighting.
            weights += 1.0 / float(len(weights))
        return weights

    def chooseFromWeights(self, weights, linklist):
        """
        Summary

        Args:
            weights (TYPE): Description
            linklist (TYPE): Description

        Returns:
            TYPE: Description
        """
        if len(weights) == 0:
            return -1
        else:
            weights = self.normalizeWeights(weights)
            return np.random.choice(list(range(0, len(linklist))), p=weights)

    def selectRouteRuleset1(self):
        """
        Summary

        Returns:
            TYPE: Description
        """
        linklen = len(self.location.links)
        weights = np.zeros(linklen)

        for i in range(0, linklen):
            if self.location.links[i].endpoint.getCapMultiplier(
                    self.location.links[i].numAgents) <= 0.000001:
                weights[i] = 0.0
            # forced redirection: if this is true for a link, return its value
            # immediately.
            elif self.location.links[i].forced_redirection is True:
                return i
            else:
                weights[i] = self.getLinkWeight(
                    self.location.links[i], SimulationSettings.AwarenessLevel)

                # Throttle down weight when occupancy is close to peak
                # capacity.
                weights[i] *= self.location.links[i].endpoint.getCapMultiplier(
                    self.location.links[i].numAgents)

        return self.chooseFromWeights(weights, self.location.links)

    def getEndPointScore(self, link):
        """
        Summary

        Args:
            link (TYPE): Description

        Returns:
            TYPE: Description
        """
        # print(link.endpoint.name, link.endpoint.scores)
        return link.endpoint.scores[1]

    def calculateLinkWeight(self, link, prior_distance, origin_names, step,
                            debug=False):
        """
        Calculates Link Weights recursively based on awareness level.
        Loops are avoided.

        Args:
            link (TYPE): Link class obj
            prior_distance (TYPE): Description
            origin_names (TYPE): Description
            step (TYPE): Description
            debug (bool, optional): Description

        Returns:
            TYPE: Description
        """
        weight = float(
            self.getEndPointScore(link) /
            float(SimulationSettings.Softening +
                  link.distance + prior_distance)
        ) * link.endpoint.getCapMultiplier(link.numAgents)

        if debug:
            print(
                "step {}, dest {}, dist {}, prior_dist {}, "
                "score {}, weight {}".format(step,
                                             link.endpoint.name,
                                             link.distance,
                                             prior_distance,
                                             self.getEndPointScore(link),
                                             weight)
            )

        if SimulationSettings.AwarenessLevel > step:
            # Traverse the tree one step further.
            for k, e in enumerate(link.endpoint.links):
                if e.endpoint.name in origin_names:
                    # Link points back to an origin, so ignore.
                    pass
                else:
                    weight = max(
                        weight,
                        self.calculateLinkWeight(
                            e,
                            prior_distance + link.distance,
                            origin_names + [link.endpoint.name],
                            step + 1, debug
                        )
                    )

        if debug:
            print("step {}, total weight returned {}".format(step, weight))
        return weight

    def selectRouteRuleset2(self, debug=False):
        """
        Summary

        Args:
            debug (bool, optional): Description

        Returns:
            TYPE: Description
        """
        linklen = len(self.location.links)
        weights = np.zeros(linklen)

        if SimulationSettings.AwarenessLevel == 0:
            return np.random.randint(0, linklen)

        for k, e in enumerate(self.location.links):
            weights[k] = self.calculateLinkWeight(
                e, 0.0, [self.location.name], 1, debug)

        return self.chooseFromWeights(weights, self.location.links)


class Location:

    """
    The base class for the Location object

    Attributes:
        camp (bool): Description
        capacity (TYPE): Description
        closed_links (list): Description
        conflict (bool): Description
        country (TYPE): Description
        foreign (bool): Description
        forward (bool): Description
        incoming_journey_lengths (list): Description
        links (list): Description
        LocationScore (float): Description
        marker (bool): Description
        movechance (float): Description
        name (TYPE): Description
        NeighbourhoodScore (float): Description
        numAgents (int): Description
        numAgentsOnRank (int): Description
        numAgentsSpawned (int): Description
        pop (TYPE): Description
        RegionScore (float): Description
        scores (TYPE): Description
        time (int): Description
        town (bool): Description
        x (TYPE): Description
        y (TYPE): Description
    """

    def __init__(self, name, x=0.0, y=0.0, movechance=0.001, capacity=-1,
                 pop=0, foreign=False, country="unknown"):
        self.name = name
        self.x = x
        self.y = y
        self.movechance = movechance
        self.links = []  # paths connecting to other towns
        # paths connecting to other towns that are closed.
        self.closed_links = []
        self.numAgents = 0  # refugee population
        # refugee population on current rank (for pflee).
        self.numAgentsOnRank = 0
        self.capacity = capacity  # refugee capacity
        self.pop = pop  # non-refugee population
        self.foreign = foreign
        self.country = country
        self.conflict = False
        self.camp = False
        self.town = False
        self.forward = False
        self.marker = False
        # keep track of the time in the simulation locally, to build in
        # capacity-related behavior.
        self.time = 0
        self.numAgentsSpawned = 0

        if isinstance(movechance, str):
            if "camp" in movechance.lower():
                self.movechance = SimulationSettings.CampMoveChance
                self.camp = True
                self.foreign = True
            elif "conflict" in movechance.lower():
                self.movechance = SimulationSettings.ConflictMoveChance
                self.conflict = True
            elif "forward" in movechance.lower():
                self.movechance = 1.0
                self.forward = True
            elif "marker" in movechance.lower():
                self.movechance = 1.0
                self.marker = True
            elif (
                "default" in movechance.lower() or "town" in movechance.lower()
            ):
                self.town = True
                self.movechance = SimulationSettings.DefaultMoveChance
            else:
                print(
                    "Error in creating Location() object: cannot parse "
                    "movechance value of {}, for location object "
                    "with name {}.".format(movechance, name)
                )

        # Automatically tags a location as a Camp if refugees are less than 2%
        # likely to move out on a given day.
        if self.movechance < 0.02 and not self.camp:
            print("Warning: automatically setting location {} to camp, "
                  "as movechance = {}".format(self.name, self.movechance),
                  file=sys.stderr
                  )
            self.camp = True
            self.town = False

        # Value of Location. Should be between 0.5 and
        # SimulationSettings.CampWeight.
        self.LocationScore = 1.0
        # Value of Neighbourhood. Should be between 0.5 and
        # SimulationSettings.CampWeight.
        self.NeighbourhoodScore = 1.0
        # Value of surrounding region. Should be between 0.5 and
        # SimulationSettings.CampWeight.
        self.RegionScore = 1.0
        self.scores = np.array([1.0, 1.0, 1.0, 1.0])

        self.updateLocationScore()
        self.updateNeighbourhoodScore()
        self.updateRegionScore()

        if SimulationSettings.CampLogLevel > 0:
            # reinitializes every time step. Contains individual journey
            # lengths from incoming agents.
            self.incoming_journey_lengths = []

        self.print()

    def SetCamp(self):
        self.movechance = SimulationSettings.CampMoveChance
        self.camp = True
        self.foreign = True
        self.conflict = False
        self.town = False

    def DecrementNumAgents(self):
        """
        Summary
        """
        self.numAgents -= 1

    def IncrementNumAgents(self):
        """
        Summary
        """
        self.numAgents += 1

    def print(self):
        print(
            "Location name: {}, X: {}, Y: {}, movechance: {}, cap: {}, "
            "pop: {}, country: {}, conflict? {}, camp? {}".format(
                self.name, self.x, self.y, self.movechance, self.capacity,
                self.pop, self.country, self.conflict, self.camp),
            file=sys.stderr
        )
        for l in self.links:
            print(
                "Link from {} to {}, dist: {}, pop. {}".format(
                    self.name, l.endpoint.name, l.distance, l.numAgents),
                file=sys.stderr
            )

    def SetConflictMoveChance(self):
        """
        Modify move chance to the default value set for conflict regions.
        """
        self.movechance = SimulationSettings.ConflictMoveChance

    def SetCampMoveChance(self):
        """ Modify move chance to the default value set for camps. """
        self.movechance = SimulationSettings.CampMoveChance

    def CalculateResidualWeightingFactor(self, residual, cap_limit,
                                         nearly_full_occ):
        """
        Calculate the residual weighting factor, when pop is between 0.9 and
        1.0 of capacity (with default settings).

        !!! note
            Weight should be 1.0 at 0.9, and 0.0 at 1.0 capacity level.

        !!! tip
            Asserts are added to prevent corruption of simulation results in
            case this function misbehaves.

        Args:
            residual (float): the residual weighting factor
            cap_limit (int): Description
            nearly_full_occ (float): Description

        Returns:
            TYPE: Description
        """

        weight = 1.0 - (residual / (cap_limit * (1.0 - nearly_full_occ)))

        assert(weight >= 0.0)
        assert(weight <= 1.0)

        return weight

    def getCapMultiplier(self, numOnLink):
        """
        Checks whether a given location has reached full capacity or is close
        to it.

        Args:
            numOnLink (TYPE): Description

        Returns:
            float:
            - 1.0 if occupancy < nearly_full_occ (0.9).
            - 0.0 if occupancy >= 1.0.
            - a value in between for intermediate values

        """
        nearly_full_occ = 0.9  # occupancy rate to be considered nearly full.
        # full occupancy limit (should be equal to self.capacity).
        cap_limit = self.capacity * SimulationSettings.CapacityBuffer

        if self.capacity < 0:
            return 1.0
        elif self.numAgents <= nearly_full_occ * cap_limit:
            return 1.0
        elif self.numAgents >= 1.0 * cap_limit:
            return 0.0

        # should be a number equal in range [0 to 0.1*self.numAgents].
        residual = self.numAgents - (nearly_full_occ * cap_limit)

        return self.CalculateResidualWeightingFactor(residual,
                                                     cap_limit,
                                                     nearly_full_occ
                                                     )

    def getScores(self, index):
        """
        Summary

        Args:
            index (TYPE): Description

        Returns:
            TYPE: Description
        """
        return self.scores[index]

    def setScore(self, index, value):
        """
        Summary

        Args:
            index (TYPE): Description
            value (TYPE): Description
        """
        self.scores[index] = value

    def updateLocationScore(self):
        """
        Attractiveness of the local point, based on local point
        information only.
        """

        if self.foreign or self.camp:
            # * max(1.0,SimulationSettings.AwarenessLevel)
            self.LocationScore = SimulationSettings.CampWeight
        elif self.conflict:
            # * max(1.0,SimulationSettings.AwarenessLevel)
            self.LocationScore = SimulationSettings.ConflictWeight
        else:
            self.LocationScore = 1.0

        self.setScore(0, 1.0)
        self.setScore(1, self.LocationScore)
        # print(self.name,self.camp,self.foreign,self.LocationScore)

    def updateNeighbourhoodScore(self):
        """
        Attractiveness of the local point, based on information from local
        and adjacent points, weighted by link length.
        """
        # No links connected or a Camp? Use LocationScore.
        if len(self.links) == 0 or self.camp:
            self.NeighbourhoodScore = self.LocationScore
            return

        self.NeighbourhoodScore = 0.0
        total_link_weight = 0.0

        for i in self.links:
            self.NeighbourhoodScore += i.endpoint.LocationScore / \
                float(i.distance)
            total_link_weight += 1.0 / float(i.distance)

        self.NeighbourhoodScore /= total_link_weight
        self.setScore(2, self.NeighbourhoodScore)

    def updateRegionScore(self):
        """
        Attractiveness of the local point, based on neighbourhood information
        from local and adjacent points, weighted by link length.
        """
        # No links connected or a Camp? Use LocationScore.
        if len(self.links) == 0 or self.camp:
            self.RegionScore = self.LocationScore
            return

        self.RegionScore = 0.0
        total_link_weight = 0.0

        for i in self.links:
            self.RegionScore += i.endpoint.NeighbourhoodScore / \
                float(i.distance)
            total_link_weight += 1.0 / float(i.distance)

        self.RegionScore /= total_link_weight
        self.setScore(3, self.RegionScore)


class Link:
    """
    A base class for Link object

    Attributes:
        closed (bool): Description
        distance (TYPE): Description
        endpoint (TYPE): Description
        forced_redirection (TYPE): Description
        name (str): Description
        numAgents (int): Description
        numAgentsOnRank (int): Description
        startpoint (TYPE): Description
    """

    def __init__(self, startpoint, endpoint, distance,
                 forced_redirection=False):
        self.name = "__link__"
        self.closed = False

        # distance in km.
        self.distance = float(distance)

        # links for now always connect two endpoints
        self.startpoint = startpoint
        self.endpoint = endpoint

        # number of agents that are in transit.
        self.numAgents = 0
        # refugee population on current rank (for pflee).
        self.numAgentsOnRank = 0

        # if True, then all Persons will go down this link.
        self.forced_redirection = forced_redirection

    def DecrementNumAgents(self):
        """
        Decrease the number of agent on the link
        """
        self.numAgents -= 1

    def IncrementNumAgents(self):
        """
        Increase the number of agent on the link
        """
        self.numAgents += 1


class Ecosystem:
    """
    a base class for Ecosystem object

    Attributes:
        agents (list): Description
        closures (list): Description
        conflict_pop (int): Description
        conflict_weights (TYPE): Description
        conflict_zone_names (list): Description
        conflict_zones (list): Description
        locationNames (list): Description
        locations (list): Description
        num_arrivals (list): Description
        print_location_output (bool): Description
        time (int): Description
        travel_durations (list): Description
    """

    def __init__(self):
        self.locations = []
        self.locationNames = []
        self.agents = []
        self.closures = []  # format [type, source, dest, start, end]
        self.time = 0
        self.print_location_output = True  # print location output data

        # Bring conflict zone management into FLEE.
        self.conflict_zones = []
        self.conflict_zone_names = []
        self.conflict_weights = np.array([])
        self.conflict_pop = 0

        if SimulationSettings.CampLogLevel > 0:
            self.num_arrivals = []  # one element per time step.
            self.travel_durations = []  # one element per time step.

    def get_camp_names(self):
        """
        Summary

        Returns:
            TYPE: Description
        """
        camp_names = []
        for l in self.locations:
            if l.camp:
                camp_names += [l.name]
        return camp_names

    def export_graph(self, use_ids_instead_of_names=False):
        """
        Summary

        Args:
            use_ids_instead_of_names (bool, optional): Description

        Returns:
            TYPE: Description
        """
        vertices = []
        edges = []
        for l in self.locations:
            vertices += [l.name]
            for p in l.links:
                edges += [[l.name, p.endpoint.name, p.distance]]

        return vertices, edges

    def _aggregate_arrivals(self):
        """
        Add up arrival statistics, to find out travel durations and total
        number of camp arrivals.
        """
        if SimulationSettings.CampLogLevel > 0:
            arrival_total = 0
            tmp_num_arrivals = 0

            for l in self.locations:
                if l.Camp is True:
                    arrival_total += np.sum(l.incoming_journey_lengths)
                    tmp_num_arrivals += len(l.incoming_journey_lengths)
                    l.incoming_journey_lengths = []

            self.num_arrivals += [tmp_num_arrivals]

            if tmp_num_arrivals > 0:
                self.travel_durations += [float(arrival_total) /
                                          float(tmp_num_arrivals)]
            else:
                self.travel_durations += [0.0]

            # print("New arrivals: ", self.travel_durations[-1],
            #       arrival_total, tmp_num_arrivals)

    def enact_border_closures(self, time, twoway=True, Debug=False):
        """
        Summary

        Args:
            time (TYPE): Description
            twoway (bool, optional): Description
            Debug (bool, optional): Description
        """
        # print("Enact border closures: ", self.closures)
        if len(self.closures) > 0:
            for c in self.closures:
                if time == c[3]:
                    if c[0] == "country":
                        if Debug:
                            print("Time = {}. Closing Border between "
                                  "[{}] and [{}]".format(time, c[1], c[2]),
                                  file=sys.stderr
                                  )
                        self.close_border(c[1], c[2], twoway)
                    if c[0] == "location":
                        self.close_location(c[1], twoway)
                    if c[0] == "link":
                        self.close_link(c[1], c[2], twoway)
                if time == c[4]:
                    if c[0] == "country":
                        if Debug:
                            print("Time = {}. Reopening Border between "
                                  "[{}] and [{}]".format(time, c[1], c[2]),
                                  file=sys.stderr
                                  )
                        self.reopen_border(c[1], c[2], twoway)
                    if c[0] == "location":
                        self.reopen_location(c[1], twoway)
                    if c[0] == "link":
                        self.reopen_link(c[1], c[2], twoway)

    def _convert_location_name_to_index(self, name):
        """
        Convert a location name to an index number

        Args:
            name (TYPE): Description

        Returns:
            TYPE: Description
        """
        x = -1
        # Convert name "startpoint" to index "x".
        for i in range(0, len(self.locations)):
            if(self.locations[i].name == name):
                x = i

        if x < 0:
            print("#Warning: location not found in remove_link")
            return False

        return x

    def _remove_link_1way(self, startpoint, endpoint, close_only=False):
        """
        Remove link in one direction (private function,
        use remove_link instead).

        Args:
            startpoint (TYPE): Description
            endpoint (TYPE): Description
            close_only (bool, optional): if True will instead move the link to
                the closed_links list of the location, rendering it inactive.

        Returns:
            TYPE: Description
        """
        new_links = []
        x = self._convert_location_name_to_index(startpoint)
        removed = False

        for i in range(0, len(self.locations[x].links)):
            if self.locations[x].links[i].endpoint.name is not endpoint:
                new_links += [self.locations[x].links[i]]
                continue
            elif close_only:
                # print("Closing [{}] to [{}]".format(startpoint, endpoint),
                #       file=sys.stderr
                #       )
                self.locations[x].links[i].closed = True
                # we copy the route link to have a backup.
                self.locations[
                    x].closed_links += [copy.copy(self.locations[x].links[i])]
                # The original object might still be used by agents as part of
                # finish_travel, but will be orphaned eventually.

                # make sure agent counts are set to 0.
                self.locations[x].closed_links[-1].numAgents = 0
                # ditto.
                self.locations[x].closed_links[-1].numAgentsOnRank = 0
            removed = True

        self.locations[x].links = new_links
        if not removed:
            print("Warning: cannot remove link from {}, "
                  "as there is no link to {}".format(startpoint, endpoint),
                  file=sys.stderr
                  )
        return removed

    def _reopen_link_1way(self, startpoint, endpoint):
        """
        Reopen a closed link.

        Args:
            startpoint (TYPE): Description
            endpoint (TYPE): Description

        Returns:
            TYPE: Description
        """
        new_closed_links = []
        x = self._convert_location_name_to_index(startpoint)
        reopened = False
        # print(
        #     "Reopening link from %s to %s, closed link list length = %s." % (
        #         startpoint, endpoint, len(self.locations[x].closed_links)
        #     ),
        #     file=sys.stderr
        # )

        for i in range(0, len(self.locations[x].closed_links)):
            if self.locations[x].closed_links[i].endpoint.name is not endpoint:
                # print("[%s] to [%s] (%s)" % (
                #     startpoint,
                #     self.locations[x].closed_links[i].endpoint.name,
                #     endpoint),
                #     file=sys.stderr
                # )
                new_closed_links += [self.locations[x].closed_links[i]]
            else:
                # print("Match: [%s] to [%s] (%s)" % (
                #     startpoint,
                #     self.locations[x].closed_links[i].endpoint.name,
                #     endpoint),
                #     file=sys.stderr
                # )
                self.locations[x].links += [self.locations[x].closed_links[i]]
                self.locations[x].links[-1].closed = False
                reopened = True

        self.locations[x].closed_links = new_closed_links
        if not reopened:
            print(
                "Warning: cannot reopen link from {}, "
                "as there is no link to {}".format(startpoint, endpoint),
                file=sys.stderr
            )
        return reopened

    def remove_link(self, startpoint, endpoint, twoway=True, close_only=False):
        """
        Removes a link between two location names.

        Args:
            startpoint (TYPE): Description
            endpoint (TYPE): Description
            twoway (bool, optional): if True, also removes link from
                `endpoint` to `startpoint`.
            close_only (bool, optional): if `True` will instead move the link
                to the closed_links list of the location, rendering it
                inactive.

        Returns:
            TYPE: Description
        """
        if twoway:
            self._remove_link_1way(endpoint, startpoint, close_only)
        return self._remove_link_1way(startpoint, endpoint, close_only)

    def reopen_link(self, startpoint, endpoint, twoway=True):
        """
        Reopens a previously closed link between two location names.

        Args:
            startpoint (TYPE): Description
            endpoint (TYPE): Description
            twoway (bool, optional): if `True`, also removes link from
                `endpoint` to `startpoint`.

        Returns:
            TYPE: Description
        """
        if twoway:
            self._reopen_link_1way(endpoint, startpoint)
        return self._reopen_link_1way(startpoint, endpoint)

    def close_link(self, startpoint, endpoint, twoway=True):
        """
        Shorthand call for remove_link, only moving the link to
        the closed list.

        Args:
            startpoint (TYPE): Description
            endpoint (TYPE): Description
            twoway (bool, optional): Description

        Returns:
            TYPE: Description
        """
        return self.remove_link(startpoint,
                                endpoint,
                                twoway=twoway,
                                close_only=True)

    def _change_location_1way(self, location_name, mode="close",
                              direction="both", Debug=False):
        """
        Close all links to or from one location.

        Args:
            location_name (TYPE): Description
            mode (str, optional): `close` or `reopen`
            direction (str, optional): `in`, `out` or `both`.
            Debug (bool, optional): Description

        Returns:
            TYPE: Description
        """

        dir_mode = 0
        if direction == "out":
            dir_mode = 1
        elif direction == "both":
            dir_mode = 2

        print("%s location 1 way [%s] in direction %s (%s)." % (
            mode, location_name, direction, dir_mode), file=sys.stderr)
        changed_anything = False

        for i in range(0, len(self.locationNames)):
            if self.locationNames[i] == location_name:
                changed_anything = True

                link_set = self.locations[i].links
                if mode == "reopen":
                    link_set = self.locations[i].closed_links

                j = 0
                while j < len(link_set):
                    if Debug:
                        print(
                            "starting to {} link "
                            "[{}] [{}] in direction {}".format(
                                mode,
                                location_name,
                                link_set[j].endpoint.name,
                                direction),
                            file=sys.stderr
                        )
                    if mode == "close":

                        if dir_mode % 2 == 0:
                            self.close_link(link_set[j].endpoint.name,
                                            self.locationNames[i],
                                            twoway=False)

                        if dir_mode > 0:
                            if self.close_link(self.locationNames[i],
                                               link_set[j].endpoint.name,
                                               twoway=False):
                                # shrink the link list. # This operation
                                # affects the overall loop, so no major
                                # operations should take place after this.
                                link_set = self.locations[i].links
                        else:
                            j += 1

                    elif mode == "reopen":

                        if dir_mode % 2 == 0:
                            self.reopen_link(link_set[j].endpoint.name,
                                             self.locationNames[i],
                                             twoway=False)

                        if dir_mode > 0:
                            if self.reopen_link(self.locationNames[i],
                                                link_set[j].endpoint.name,
                                                twoway=False):
                                # shrink the closed link list. This operation
                                # affects the overall loop, so no major
                                # operations should take place after this.
                                link_set = self.locations[i].closed_links
                            else:
                                j += 1

        return changed_anything

    def _change_border_1way(self, source_country, dest_country, mode="close",
                            Debug=False):
        """
        Close all links between two countries in one direction.

        Args:
            source_country (TYPE): Description
            dest_country (TYPE): Description
            mode (str, optional): Description
            Debug (bool, optional): Description
        """
        # print("{} border 1 way [{}] [{}]".format(
        #     mode, source_country, dest_country),
        #     file=sys.stderr
        # )
        changed_anything = False
        for i in range(0, len(self.locationNames)):
            if self.locations[i].country == source_country:

                link_set = self.locations[i].links
                if mode == "reopen":
                    link_set = self.locations[i].closed_links

                j = 0
                while j < len(link_set):
                    if link_set[j].endpoint.country == dest_country:
                        if Debug:
                            print("starting to {} border 1 way "
                                  "[{}/{}] [{}/{}]".format(
                                      mode,
                                      source_country,
                                      self.locations[i].name,
                                      dest_country,
                                      link_set[j].endpoint.name),
                                  file=sys.stderr
                                  )
                        changed_anything = True
                        if mode == "close":
                            if self.close_link(self.locationNames[i],
                                               link_set[j].endpoint.name,
                                               twoway=False):
                                link_set = self.locations[i].links
                                continue
                        elif mode == "reopen":
                            if self.reopen_link(self.locationNames[i],
                                                link_set[j].endpoint.name,
                                                twoway=False):
                                link_set = self.locations[i].closed_links
                                continue
                    j += 1

        if not changed_anything:
            print(
                "Warning: no link closed when closing borders between "
                "{} and {}.".format(source_country, dest_country),
                file=sys.stderr
            )

    def close_border(self, source_country, dest_country, twoway=True,
                     Debug=False):
        """
        Close all links between two countries.

        Args:
            source_country (TYPE): Description
            dest_country (TYPE): Description
            twoway (bool, optional): if `False`, only links from source to
                destination will be closed
            Debug (bool, optional): Description
        """
        self._change_border_1way(
            source_country, dest_country, mode="close", Debug=Debug)
        if twoway:
            self._change_border_1way(
                dest_country, source_country, mode="close", Debug=Debug)

    def reopen_border(self, source_country, dest_country, twoway=True,
                      Debug=False):
        """
        Re-open all links between two countries.

        Args:
            source_country (TYPE): Description
            dest_country (TYPE): Description
            twoway (bool, optional): if `False`, only links from source to
                destination will be closed
            Debug (bool, optional): Description
        """
        self._change_border_1way(
            source_country, dest_country, mode="reopen", Debug=Debug)
        if twoway:
            self._change_border_1way(
                dest_country, source_country, mode="reopen", Debug=Debug)

    def close_location(self, location_name, twoway=True, Debug=False):
        """
        Close in- and outgoing links for a location.

        Args:
            location_name (TYPE): Description
            twoway (bool, optional): Description
            Debug (bool, optional): Description

        Returns:
            TYPE: Description
        """
        if twoway:
            return self._change_location_1way(location_name,
                                              mode="close",
                                              direction="both",
                                              Debug=Debug
                                              )
        else:
            return self._change_location_1way(location_name,
                                              mode="close",
                                              direction="in",
                                              Debug=Debug
                                              )

    def reopen_location(self, location_name, twoway=True, Debug=False):
        """
        Reopen in- and outgoing links for a location.

        Args:
            location_name (TYPE): Description
            twoway (bool, optional): Description
            Debug (bool, optional): Description
        """
        if twoway:
            self._change_location_1way(
                location_name, mode="reopen", direction="both", Debug=Debug)
        else:
            self._change_location_1way(
                location_name, mode="reopen", direction="in", Debug=Debug)

    def add_conflict_zone(self, name, change_movechance=True):
        """
        Adds a conflict zone. Default weight is equal to population of
        the location.

        Args:
            name (TYPE): Description
            change_movechance (bool, optional): Description

        Returns:
            TYPE: Description
        """
        for i in range(0, len(self.locationNames)):
            if self.locationNames[i] == name:
                if name not in self.conflict_zone_names:
                    if change_movechance:
                        self.locations[i].movechance = (
                            SimulationSettings.ConflictMoveChance
                        )
                        self.locations[i].conflict = True
                        self.locations[i].town = False

                    self.conflict_zone_names += [name]
                    self.conflict_zones += [self.locations[i]]
                    self.conflict_weights = np.append(
                        self.conflict_weights, [self.locations[i].pop])
                    self.conflict_pop = sum(self.conflict_weights)
                    if SimulationSettings.InitLogLevel > 0:
                        print("Added conflict zone:", name,
                              ", pop. ", self.locations[i].pop)
                        print("New total pop. in conflict zones: ",
                              self.conflict_pop)
                    return

        print("Diagnostic: self.locationNames: ", self.locationNames)
        print(
            "ERROR in flee.add_conflict_zone: location with name [{}] appears"
            " not to exist in the FLEE ecosystem "
            "(see diagnostic above).".format(name)
        )

    def remove_conflict_zone(self, name, change_movechance=True):
        """
        Shorthand function to remove a conflict zone from the list.
        (not used yet)

        Args:
            name (TYPE): Description
            change_movechance (bool, optional): Description
        """
        new_conflict_zones = []
        new_conflict_zone_names = []
        new_weights = np.array([])

        for i in range(0, len(self.conflict_zones)):
            if self.conflict_zones[i].name is not name:
                new_conflict_zones += [self.conflict_zones[i]]
                new_conflict_zone_names += [self.conflict_zone_names[i]]
                new_weights = np.append(
                    new_weights, [self.conflict_weights[i]])
            else:
                if change_movechance:
                    self.conflict_zones[
                        i].movechance = SimulationSettings.DefaultMoveChance
                self.conflict_zones[i].conflict = False
                self.conflict_zones[i].town = True

        self.conflict_zone_names = new_conflict_zone_names
        self.conflict_zones = new_conflict_zones
        self.conflict_weights = new_weights
        self.conflict_pop = sum(self.conflict_weights)

    def pick_conflict_location(self):
        """
        Summary

        Returns:
            TYPE: Description
        """
        # print(
        #     "Warning: this function is now deprecated as of ruleset 2.0. "
        #     "Please use pick_conflict_locations() instead in your scripts.",
        #     file=sys.stderr
        # )
        return self.pick_conflict_locations(1)[0]

    def pick_conflict_locations(self, number=1):
        """
        Returns a weighted random element from the list of conflict locations.

        Args:
            number (int, optional): Description

        Returns:
            TYPE: returns a number, which is an index in the array of
                conflict locations.
        """
        assert self.conflict_pop > 0

        return np.random.choice(self.conflict_zones,
                                number,
                                p=self.conflict_weights / self.conflict_pop
                                )

    def add_agents_to_conflict_zones(self, number):
        """
        Add a group of agents, distributed across conflict zones.

        Args:
            number (TYPE): Description
        """
        cl = self.pick_conflict_locations(number)
        for i in range(0, number):
            self.addAgent(cl[i])

    def refresh_conflict_weights(self):
        """
        This function needs to be called when
        SimulationSettings.TakeRefugeesFromPopulation is set to True.
        It will update the weights to reflect the new population numbers.
        """
        for i in range(0, len(self.conflict_zones)):
            self.conflict_weights[i] = self.conflict_zones[i].pop
        self.conflict_pop = sum(self.conflict_weights)

    def evolve(self):
        """
        Summary
        """
        # update level 1, 2 and 3 location scores
        for l in self.locations:
            l.time = self.time
            l.updateLocationScore()

        for l in self.locations:
            l.updateNeighbourhoodScore()

        for l in self.locations:
            l.updateRegionScore()

        # update agent locations
        for a in self.agents:
            a.evolve()

        for a in self.agents:
            a.finish_travel()
            a.timesteps_since_departure += 1

        if SimulationSettings.AgentLogLevel > 0:
            write_agents(self.agents, self.time)

        for a in self.agents:
            a.recent_travel_distance = (
                a.recent_travel_distance +
                (a.distance_moved_this_timestep /
                    SimulationSettings.MaxMoveSpeed
                 )
            ) / 2.0
            a.distance_moved_this_timestep = 0

        # update link properties
        if SimulationSettings.CampLogLevel > 0:
            self._aggregate_arrivals()

        self.time += 1

    def addLocation(self, name, x="0.0", y="0.0",
                    movechance=SimulationSettings.DefaultMoveChance,
                    capacity=-1, pop=0, foreign=False, country="unknown"):
        """
        Add a location to the ABM network graph

        Args:
            name (TYPE): Description
            x (str, optional): Description
            y (str, optional): Description
            movechance (TYPE, optional): Description
            capacity (TYPE, optional): Description
            pop (int, optional): Description
            foreign (bool, optional): Description
            country (str, optional): Description

        Returns:
            TYPE: location object (Link class)
        """
        l = Location(name, x, y, movechance, capacity, pop, foreign, country)
        if SimulationSettings.InitLogLevel > 0 and self.print_location_output:
            print("Location:", name, x, y, l.movechance,
                  capacity, ", pop. ", pop, foreign)
        self.locations.append(l)
        self.locationNames.append(l.name)
        return l

    def addAgent(self, location):
        """
        Add an agent to the location object

        Args:
            location (Link): location object
        """
        if SimulationSettings.TakeRefugeesFromPopulation:
            if location.conflict:
                if location.pop > 0:
                    location.pop -= 1
                    location.numAgentsSpawned += 1
                else:
                    print("ERROR: Number of agents in the simulation is "
                          "larger than the combined population of the conflict"
                          " zones. Please amend locations.csv.")
                    location.print()
                    assert location.pop > 1

        self.agents.append(Person(location))

    def insertAgent(self, location):
        """
        insert Agent does NOT take from Population.

        Args:
            location (Location): location object
        """
        self.agents.append(Person(location))

    def insertAgents(self, location, number):
        """
        Summary

        Args:
            location (TYPE): Description
            number (TYPE): Description
        """
        for i in range(0, number):
            self.insertAgent(location)

    def clearLocationsFromAgents(self, location_names):
        """
        Remove all agents from a list of locations by name.
        Useful for couplings to other simulation codes.

        Args:
            location_names (TYPE): Description
        """
        new_agents = []
        for i in range(0, len(self.agents)):
            if self.agents[i].location.name not in location_names:
                new_agents += agents[i]  # agent is preserved in ecosystem
            else:
                # agent is removed from the ecosystem and number of agents
                # drops by one.
                self.agents[i].location.DecrementNumAgents()
        self.agents = new_agents

    def numAgents(self):
        """
        Summary

        Returns:
            TYPE: Description
        """
        return len(self.agents)

    def linkUp(self, endpoint1, endpoint2, distance="1.0",
               forced_redirection=False):
        """
        Creates a link between two endpoint locations

        Args:
            endpoint1 (TYPE): Description
            endpoint2 (TYPE): Description
            distance (str, optional): Description
            forced_redirection (bool, optional): Description
        """
        endpoint1_index = -1
        endpoint2_index = -1
        for i in range(0, len(self.locationNames)):
            if(self.locationNames[i] == endpoint1):
                endpoint1_index = i
            if(self.locationNames[i] == endpoint2):
                endpoint2_index = i

        if endpoint1_index < 0:
            print("Diagnostic: Ecosystem.locationNames: ", self.locationNames)
            print("Error: link created to non-existent source: ",
                  endpoint1, " with dest ", endpoint2)
            sys.exit()
        if endpoint2_index < 0:
            print("Diagnostic: Ecosystem.locationNames: ", self.locationNames)
            print("Error: link created to non-existent destination: ",
                  endpoint2, " with source ", endpoint1)
            sys.exit()

        self.locations[endpoint1_index].links.append(
            Link(self.locations[endpoint1_index],
                 self.locations[endpoint2_index],
                 distance,
                 forced_redirection
                 )
        )
        self.locations[endpoint2_index].links.append(
            Link(self.locations[endpoint2_index],
                 self.locations[endpoint1_index],
                 distance
                 )
        )

    def printInfo(self):
        """
        Summary
        """
        print("Time: ", self.time, ", # of agents: ", len(self.agents))
        for l in self.locations:
            print(l.name, l.numAgents, file=sys.stderr)

    def printComplete(self):
        """
        Summary
        """
        print("Time: ", self.time, ", # of agents: ", len(self.agents))
        if self.print_location_output:
            for l in self.locations:
                print("Location name %s, number of agents %s" %
                      (l.name, l.numAgents), file=sys.stderr)
                l.print()

    def getRankN(self, i):
        """
        Returns whether this process should do a task.

        Args:
            i (int): Description

        Returns:
            bool: Always returns true, as flee.py is sequential.
        """
        return True
