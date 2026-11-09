"""Optional Tinker integration: remote LoRA training, with sampling on Tinker or on Aster's serving engines.

Deployment/config discovery does not import the SDK. ``component`` is the training component that runs each job
in process (``aster.train.local_jobs.LocalJobComponent``): ``parameters`` parses the job's parameters, ``objectives`` names its method,
``preparation`` cuts the job's data into optimizer steps, ``rollout`` runs a task job's rollouts, ``losses`` names each step's Tinker loss and shapes its inputs, and
``client`` is the training SDK boundary. The SDK pieces that training and serving share, the checkpoint manifest,
the SDK session and sampling, are ``aster.tinker``. Sampling on Tinker itself is ``aster.inference.tinker``; serving
on engines is ``aster.inference.serving``. Each side reads the checkpoint a snapshot carries.
"""
