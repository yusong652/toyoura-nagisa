# PFC Script: Get all ball IDs
# Returns a list of all ball IDs in the simulation

balls = itasca.ball.list()
result = [b.id() for b in balls]
