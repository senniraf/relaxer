# relaxer

relaxer is a prototype tool implementing the bounded relaxations of timed automata. It computes the relaxations for UPPAAL models.

## Structure

This directory is structured in the following way:

* `evaluation`: Contains the results and inputs from the evaluation part of the submitted formats23 paper. The input models are found in `evaluation/models`, the configurations are found in `evaluation/formats23/configs` and the results are found in the top folder.
* `relaxer` contains the source code of the relaxer python module.
* `res`: contains different models and configs.
* `.gitignore`: The .gitignore file.
* `Dockerfile`: The Dockerfile for building the relaxer docker image.
* `install.sh`: The install script.
* `Pipfile` and `Pipfile.lock`: The pipenv files for dependency management and creating the virtual python environment.

## Installation

### Docker (recommended)

The recommended installation of the relaxer tool is to build its docker image. The only tool needed for this is Docker which can be downloaded from their [Website](https://www.docker.com/). The docker image is built with:

```sh
docker build -t relaxer .
```

With this, relaxer can be executed using the docker image:

```sh
docker run --volume=$PWD/res:/app/res:ro --volume=$PWD/out:/app/out --name relaxer-getting-started relaxer --config res/Double-Path-3-relax.json
```

### Install Script

The install script `install.sh` installs all necessary packages on ubuntu systems:

```sh
./install.sh
```

If relaxer is installed using this script virtual python environment is created with pipenv. You can open a shell in the virtual environment by executing

```sh
pipenv shell
```

## Usage

Note: We are assuming that you are on a shell inside the pipenv virtual environment if you installed relaxer with the install script. If you installed relaxer by building the docker image, you can load sub-directories of your current work directory into the container by adding the `--volume $PWD/dir:/app/dir` flag to the `docker run` command.

relaxer takes a config as an input file containing all necessary information. The command to execute is

```sh
docker run --volume=$PWD/res:/app/res:ro --volume=$PWD/out:/app/out relaxer --config res/Double-Path-3-relax.json
```

if you built the docker image or

```sh
python -m relaxer -c ./res/Double-Path-3-relax.json
```

if you used the install script. The config is a json file.

**Example:**

```json
{
    "inputs": [
        {
            "type": "UPPAAL",
            "model": {
                "path": "res/models/Double-Path-3-relax.xml"
            },
            "invariant_relaxations": [
                {
                    "location_id": "id2",
                    "clock_constraint": "c <= 1"
                },
                {
                    "location_id": "id3",
                    "clock_constraint": "d <= 2"
                }
            ],
            "guard_relaxations": [
                {
                    "source_id": "id0",
                    "target_id": "id2",
                    "clock_constraint": "a >= 2"
                }
            ],
            "depth": 10
        }
    ],
    "output": {
        "type": "file",
        "path": "out/Double-Path-3-relax.json"
    },
    "stats": {
        "type": "json",
        "path": "out/Double-Path-3-relax.stats.json"
    },
    "debug": false,
    "dump": {
        "type": "directory",
        "path": "out/dump"
    }
}
```

This example calculates the upper bounds for the given location invariants and guards using `res/models/Double-Path-3-relax.xml` as an input model. The `location_id` of a location can be found by opening the UPPAAL xml model file in a text editor. The bounded length of STTs is given by `depth`. The results are written to the `output` file and the statistics are written to the `stats` file. If a `dump` is given, relaxer will write intermediate results to the specified directory.

**Example Output:**

```json
[
    {
        "model": "res/models/Double-Path-3-relax.xml",
        "timestamp": "2023-02-28T17:40:41.686637+00:00",
        "invariant_relaxations": [
            {
                "location_id": "id2",
                "clock_constraint": "c<=1"
            },
            {
                "location_id": "id3",
                "clock_constraint": "d<=2"
            }
        ],
        "guard_relaxations": [
            {
                "source_id": "id0",
                "target_id": "id2",
                "clock_constraint": "a>=2"
            }
        ],
        "depth": 10,
        "supported_solution": true,
        "solution": [
            [
                2.0,
                0.0,
                "inf"
            ],
            [
                0.0,
                2.0,
                "inf"
            ]
        ]
    }
]
```

The solutions are listed in `solution`. Every solution is an array of the amount by which the bound of every clock constraint can be increased/decreased. The index of the value is the index of the constraint in the combined array `[invariant_relaxation + guard_relaxation]`. In the example above, the location invariants could be relaxed by either 2 or 0 respectively. An relaxation value of `"inf"` means that the clock constraint can be removed.

**Example stats file:**

```json
[
    {
        "model": "res/models/Double-Path-3-relax.xml",
        "timestamp": "2023-02-28T17:40:41.686637+00:00",
        "total_tg_and_qe_runtime_s": 0.1943087720000003,
        "trace_generation_method": "DFS",
        "quantifier_elimination_method": "MATHSAT Fourier-Motzkin",
        "trace_generation_runtime_s": 0.014956793999999274,
        "processing_runtime_s": 0.09504327599999884,
        "quantifier_elimination_runtime_s": 0.08394393899999919,
        "number_of_traces": 13,
        "num_relaxations": 3,
        "num_terms": 1,
        "optimization_runtime_s": 0.0006634209999996088,
        "supported_optima": true,
        "optimization_method": "CDD",
        "depth": 10,
        "grid_points": 11,
        "num_solutions": 2
    },
    {
        "model": "res/models/Double-Path-3-relax.xml",
        "timestamp": "2023-03-01T07:16:02.592673+00:00",
        "total_tg_and_qe_runtime_s": 0.21352572799999958,
        "trace_generation_method": "DFS",
        "quantifier_elimination_method": "MATHSAT Fourier-Motzkin",
        "trace_generation_runtime_s": 0.016871908999998908,
        "processing_runtime_s": 0.10283617000000289,
        "quantifier_elimination_runtime_s": 0.09328715799999898,
        "number_of_traces": 13,
        "num_relaxations": 3,
        "num_terms": 1,
        "optimization_runtime_s": 0.0006972679999996956,
        "supported_optima": true,
        "optimization_method": "CDD",
        "depth": 10,
        "grid_points": 11,
        "num_solutions": 2
    }
]
```

The runtimes represent the following:

* `trace_generation_runtime_s`: The time needed for performing the DFS trace generation.
* `processing_runtime_s`: The time for encoding and transforming the formulas. Includes real interval propagation and DNF transformation.
* `quantifier_elimination_runtime_s`: The time for eliminating the quantifiers.
* `total_tg_and_qe_runtime_s`: The sum of the runtimes above and additionally the time for dumping the intermediate results in these steps.
* `optimization_runtime`: The total time for solving the optimization problem.
