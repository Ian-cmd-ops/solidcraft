Robustness seed 55 ends with an invalid body ("Body1: 1 face(s) don't mesh"). `solidcraft-cli fuzz-one 55 --steps 8 --minimise` shrinks it to four commands. All values below are from main 843c548.

## Steps

```json
[{"command":"solid.box","params":{"height":25.0,"length":35.0,"width":35.0}},
 {"command":"solid.sphere","params":{"center":[10.0,35.0,10.0],"operation":"cut","radius":10.0}},
 {"command":"solid.pattern.circular","params":{"axis":"Z","count":6,"features":["Sphere1"]}},
 {"command":"solid.sphere","params":{"center":[32.5,15.0,0.0],"operation":"cut","radius":10.0}}]
```

Of the five new copies, only the one at 300° meets the box. It is centred at (35.311, 8.840, 10).

## Expected and actual

| Case (`solidcraft-cli eval`) | Volume mm³ | Bounding box max X | Kernel faces / edges |
|---|---|---|---|
| Box, Sphere1, pattern | 26552.52 | 35.0 | 17 / 42 |
| Box, Sphere1, the 300° sphere cut by hand | 26552.38 | 35.0 | 16 / 39 |
| Box, Sphere1, pattern, last sphere | **24788.71** | **41.657** | 22 / 57 |
| Box, Sphere1, the 300° sphere by hand, last sphere | 25646.15 | 35.0 | 21 / 54 |

A Monte Carlo estimate of the box minus the three spheres gives 25645.3 mm³ (40 million points, standard error 1.8). So the hand-built route is right. The route through the pattern loses 857 mm³ and reaches 6.7 mm past the box's X = 35 face.

## What differs

The pattern gives the same volume as the hand-built cut, to 0.14 mm³. But its body has one more kernel face, three more edges and two more vertices. The last sphere cut goes wrong only on the body from the pattern. I have not found which face or edge causes it.
