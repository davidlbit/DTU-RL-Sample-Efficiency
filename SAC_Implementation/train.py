## Imports
import pickle
import sys
import time
from datetime import datetime
from timeit import timeit
from typing import Dict

import numpy as np

import torch

from SAC_Implementation.SACAlgorithm import SACAlgorithm
from VideoRecorder import VideoRecorder
from plotter import Plotter

from hyperopt import fmin, tpe, space_eval, Trials, STATUS_OK

import logging
import dmc2gym
import LogHelper
from SAC_Implementation.ReplayBuffer import ReplayBuffer
from SAC_Implementation.Networks import SoftQNetwork, PolicyNetwork


def initialize_environment(domain_name, task_name, seed, frame_skip):
    # env = dmc2gym.make(domain_name="walker",
    #                    task_name="walk",
    #                    seed=1,
    #                    frame_skip=1)

    LogHelper.print_step_log(f"Initialize Environment: {domain_name}/{task_name} ...")

    env = dmc2gym.make(domain_name=domain_name,
                       task_name=task_name,
                       seed=seed,
                       frame_skip=frame_skip)

    # Debug logging to check environment specs
    s = env.reset()
    a = env.action_space.sample()
    action_dim = env.action_space.shape[0]
    state_dim = env.observation_space.shape[0]

    logging.debug(f'Sample state: {s}')
    logging.debug(f'Sample action:{a}')
    logging.debug(f'State DIM: {state_dim}')
    logging.debug(f'Action DIM:{action_dim}')

    return env, action_dim, state_dim


def show_replay():
    """
    Not-so-elegant way to display the MP4 file generated by the Monitor wrapper inside a notebook.
    The Monitor wrapper dumps the replay to a local file that we then display as a HTML video object.
    """
    import io
    import base64
    from IPython.display import HTML
    video = io.open('./gym-results/openaigym.video.%s.video000000.mp4' % env.file_infix, 'r+b').read()
    encoded = base64.b64encode(video)
    return HTML(data='''
        <video width="360" height="auto" alt="test" controls><source src="data:video/mp4;base64,{0}" type="video/mp4" /></video>'''
                .format(encoded.decode('ascii')))


def prepare_hyperparameter_tuning(hyperparameter_space, max_evals=2):
    try:
        trials = Trials()
        best = fmin(run_sac,
                    hyperparameter_space,
                    algo=tpe.suggest,
                    trials=trials,
                    max_evals=max_evals)

        logging.info("WE ARE DONE. THE BEST TRIAL IS:")
        LogHelper.print_dict({**hyperparameter_space, **best}, "Final Parameters")

        filename = datetime.now().strftime("%d_%m_%Y-%H_%M_%S")
        file_path = f"results/hp_result_{filename}.model"

        with open(file_path, 'wb') as f:
            pickle.dump(trials.results, f)
        f.close()

        logging.info("--------------------------------------------")
        logging.info(f"For more information see {file_path}")
        # return run_sac(hyperparameter_space)
    except KeyboardInterrupt as e:
        logging.error("KEYBOARD INTERRUPT")
        raise


def run_sac(hyperparameter_space: dict) -> Dict:
    """
    Method to to start the SAC algorithm on a certain problem
    :param video: video object
    :param hyperparameter_space: Dict with the hyperparameter from the Argument parser
    :return:
    """
    LogHelper.print_big_log('Initialize Hyperparameter')

    # Initialize video object

    DEFAULT_VIDEO_DIR = "videos"
    video = VideoRecorder(DEFAULT_VIDEO_DIR if hyperparameter_space.get('save_video') else None)

    # Print the hyperparameters
    # Initialize the environment
    env, action_dim, state_dim = initialize_environment(domain_name=hyperparameter_space.get('env_domain'),
                                                        task_name=hyperparameter_space.get('env_task'),
                                                        seed=hyperparameter_space.get('seed'),
                                                        frame_skip=hyperparameter_space.get('frame_skip'))

    LogHelper.print_dict(hyperparameter_space, "Hyperparameter")
    LogHelper.print_big_log("Start Training")
    sac = SACAlgorithm(env=env,
                       param={
                           "hidden_dim": hyperparameter_space.get('hidden_dim'),
                           "lr_critic": hyperparameter_space.get('lr_critic'),
                           "lr_actor": hyperparameter_space.get('lr_actor'),
                           "alpha": hyperparameter_space.get('alpha'),
                           "tau": hyperparameter_space.get('tau'),
                           "gamma": hyperparameter_space.get('gamma'),
                           "sample_batch_size": hyperparameter_space.get('sample_batch_size'),
                           "replay_buffer_size": hyperparameter_space.get('replay_buffer_size'),
                           "gpu_device": hyperparameter_space.get('gpu_device'),
                           "policy_function": hyperparameter_space.get('policy_function')
                       })

    # Init the Plotter
    plotter = Plotter(hyperparameter_space.get('episodes'))
    # initialize video

    video.init()
    recording_interval = hyperparameter_space.get('recording_interval')

    try:
        for _episode in range(hyperparameter_space.get('episodes')):
            _start = time.time()

            logging.debug(f"Start EPISODE {_episode + 1}")
            ep_reward, policy_loss_incr, q_loss_incr, length = 0, 0, 0, 0

            # Observe state and action
            current_state = env.reset()

            for step in range(hyperparameter_space.get('max_steps')):

                # Do the next step
                if _episode > -1:
                    action_mean, _ = sac.sample_action(torch.Tensor(current_state))
                else:
                    action_mean = env.action_space.sample()

                s1, r, done, _ = env.step(np.array(action_mean))

                if (step + 1) == int(hyperparameter_space.get('max_steps')):
                    done = False

                logging.debug(
                    f"--EPISODE {(str(_episode + 1).ljust(2))}.{str(step).ljust(4)} | {LogHelper.colored_log_text(f'rew: {r:.4f}', 'DARKGREEN')} | action: {action_mean} ")

                sac.buffer.add(obs=current_state, action=action_mean, reward=r, next_obs=s1, done=done)
                ep_reward += r

                _polo, _qlo = [], []
                if sac.buffer.length > sac.sample_batch_size:

                    update_steps = sac.sample_batch_size if (_episode * 250 + step) == sac.sample_batch_size == 0 else 1
                    for i in range(update_steps):
                        # Update the network
                        _metric = sac.update(step)
                        _polo.append(_metric[0])
                        _qlo.append(_metric[1])
                        logging.warning(_polo)

                    policy_loss_incr = min(_polo)
                    q_loss_incr += min(_qlo)
                    length = step

                # Update current step
                current_state = s1

                if _episode % recording_interval == 0:
                    video.record(env)

                if bool(done):
                    break

            if _episode % recording_interval == 0:
                video.save(_episode)
                video.reset()
                logging.debug("Save video")

            # for graph
            plotter.add_to_lists(reward=ep_reward,
                                 length=length,
                                 policy_loss=policy_loss_incr,
                                 q_loss=q_loss_incr)

            _end = time.time()
            if _episode % 1 == 0:
                logging.info(
                    f"EPISODE {str(_episode + 1).ljust(4)} |reward {ep_reward:.4f} | P-Loss {policy_loss_incr:.4f} | time {_end-_start:0.2f}s")
            else:
                logging.debug(
                    f"EPISODE {str(_episode + 1).ljust(4)} | reward {ep_reward:.4f} | policy-loss {policy_loss_incr:.4f}")

    except KeyboardInterrupt as e:
        logging.error("KEYBOARD INTERRUPT")
        raise
    finally:
        plotter.plot()

    rew, _, q_losses, policy_losses = plotter.get_lists()

    # Give back the error which should be optimized by the hyperparameter tuner
    max_reward = max(np.array(rew))
    return {'loss': -max_reward,
            'status': STATUS_OK,
            'model': sac,
            'max_reward': max_reward,
            'q_losses': q_losses,
            'policy_losses': policy_losses,
            'rewards': rew}
