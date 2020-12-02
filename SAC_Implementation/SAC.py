## Imports

import pickle
import sys
from datetime import datetime
from typing import Dict

from matplotlib import pyplot as plt
import numpy as np

import torch

from SAC_Implementation.SACAlgorithm import SACAlgorithm
from plotter import Plotter
import json

from hyperopt import fmin, tpe, space_eval, Trials, STATUS_OK

import logging
import dmc2gym
import LogHelper
from SAC_Implementation.ReplayBuffer import ReplayBuffer
from SAC_Implementation.networks import ValueNetwork, SoftQNetwork, PolicyNetwork


def initialize_environment(domain_name, task_name, seed, frame_skip):
    # env = dmc2gym.make(domain_name="walker",
    #                    task_name="walk",
    #                    seed=1,
    #                    frame_skip=1)
    env = dmc2gym.make(domain_name="cartpole",
                       task_name="balance",
                       seed=1,
                       frame_skip=1)

    s = env.reset()
    a = env.action_space.sample()
    logging.debug(f'sample state: {s}')
    logging.debug(f'sample action:{a}')
    ## frame skip = 4
    ## Card pole = 8
    ## Finka task = 2
    # Hyperparameters
    action_dim = env.action_space.shape[0]
    state_dim = env.observation_space.shape[0]

    ##
    logging.debug(f'state shape: {state_dim}')
    logging.debug(f'action shape: {action_dim}')

    episodes = hyperparameter_space.get('episodes')
    sample_batch_size = hyperparameter_space.get('sample_batch_size')

    gamma = hyperparameter_space.get('gamma')

    update_episodes = hyperparameter_space.get('update_episodes')
    hidden_dim = hyperparameter_space.get('hidden_dim')
    lr_critic = hyperparameter_space.get('lr_critic')  # you know this by now
    lr_actor = hyperparameter_space.get('lr_actor')  # you know this by now
    lr_policy = hyperparameter_space.get('lr_policy')  # you know this by now
    discount_factor = hyperparameter_space.get('discount_factor')  # reward discount factor (gamma), 1.0 = no discount
    replay_buffer_size = hyperparameter_space.get('replay_buffer_size')
    n_hidden_layer = hyperparameter_space.get('n_hidden_layer')
    n_hidden = hyperparameter_space.get('n_hidden')
    target_smoothing = hyperparameter_space.get('target_smoothing')
    val_freq = hyperparameter_space.get('val_freq')  # validation frequency
    episodes = hyperparameter_space.get('episodes')
    alpha = hyperparameter_space.get('alpha')
    tau = hyperparameter_space.get('tau')
    # optimizer = optim.Adam(nn.parameters(), lr=learning_rate)

    # Print the hyperparameters
    log_helper.print_dict(hyperparameter_space, "Hyperparameter")
    log_helper.print_big_log("Start Training")

    # Initialization of the Networks
    # ### Actor The actor tries to mimic the Environment and tries to find the expected reward using the next state
    # and the action (from the policy network)

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


def get_variable(x):
    """ Converts tensors to cuda, if available. """
    if torch.cuda.is_available():
        return x.cuda()
    return x


def get_numpy(x):
    """ Get numpy array for both cuda and not. """
    if torch.cuda.is_available():
        return x.cpu().data.numpy()
    return x.data.numpy()


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
    :param hyperparameter_space: Dict with the hyperparameter from the Argument parser
    :return:
    """
    LogHelper.print_big_log('Initialize Hyperparameter')

    # Print the hyperparameters
    # Initialize the environment
    env, action_dim, state_dim = initialize_environment(domain_name=hyperparameter_space.get('env_domain'),
                                                        task_name=hyperparameter_space.get('env_task'),
                                                        seed=hyperparameter_space.get('seed'),
                                                        frame_skip=hyperparameter_space.get('frame_skip'))

    LogHelper.print_dict(hyperparameter_space, "Hyperparameter")
    LogHelper.print_big_log("Start Training")
    logging.debug(hyperparameter_space)
    sac = SACAlgorithm(env=env,
                       param={
                           "hidden_dim": hyperparameter_space.get('hidden_dim'),
                           "lr_critic": hyperparameter_space.get('lr_critic'),
                           "lr_actor": hyperparameter_space.get('lr_actor'),
                           "alpha": hyperparameter_space.get('alpha'),
                           "tau": hyperparameter_space.get('tau'),
                           "gamma": hyperparameter_space.get('gamma'),
                           "sample_batch_size": hyperparameter_space.get('sample_batch_size'),
                           "replay_buffer_size": hyperparameter_space.get('replay_buffer_size')
                       })

    # Init the Plotter
    plotter = Plotter(hyperparameter_space.get('episodes'))
    try:
        for _episode in range(episodes):
            # for graph
            ep_reward, policy_loss_incr, q_loss_incr = 0, 0, 0
            for i in range(sample_batch_size):
                logging.debug(f"Episode {_episode+1}")

                # Observe state and action
                current_state = env.reset()
                # The policy network returns the mean and the std of the action. However, we only need an action to start
                action_mean, _ = policy(torch.Tensor(current_state))

            for step in range(100000):  # range(hyperparameter_space.get('max_steps')):
                # Do the next step
                logging.debug(f"Our action we chose is : {action_mean}")
                s1, r, done, _ = env.step(np.array(action_mean.detach()))
                buffer.add(obs=current_state, action=action_mean.detach(), reward=r, next_obs=s1, done=done)
                ep_reward += r

            if bool(done):
                break



            for _up_epi in range(update_episodes):
                logging.debug(f"Episode {_episode + 1} | {_up_epi + 1}")

                soft_q1.optimizer.zero_grad()
                soft_q2.optimizer.zero_grad()

                # Sample from Replay buffer
                state, action, reward, new_state, done, _ = buffer.sample(batch_size=sample_batch_size)

                # Computation of targets
                # Here we are using 2 different Q Networks and afterwards choose the lower reward as regulator.
                y_hat_q1 = soft_q1_targets(state.float(), action.float())
                y_hat_q2 = soft_q2_targets(state.float(), action.float())
                y_hat_q = torch.min(y_hat_q1, y_hat_q2)

                # Sample the action for the new state using the policy network
                action, action_entropy = policy.sample(torch.Tensor(new_state))

                # We calculate the estimated reward for the next state
                # TODO Check the average (We take the mean of the entropy right now)
                y_hat = reward + gamma * (1 - done) * (y_hat_q - action_entropy)

                ## UPDATES OF THE CRITIC NETWORKS

                q1_forward = soft_q1(state.float(), action.float())
                q2_forward = soft_q2(state.float(), action.float())

                # Q1 Network
                q_loss = F.mse_loss(q1_forward.float(), y_hat.float())\
                         + F.mse_loss(q2_forward.float(), y_hat.float())
                soft_q1.optimizer.zero_grad()
                soft_q2.optimizer.zero_grad()
                q_loss.backward()
                soft_q1.optimizer.step()
                soft_q2.optimizer.step()

                # q1_forward = soft_q1(state.float(), action.float())
                # q1_loss = F.mse_loss(q1_forward.float(), y_hat.float())
                # q1_loss.backward(retain_graph=True)
                # soft_q1.optimizer.step()
                #
                # # Q2 Network
                # q2_forward = soft_q2(state.float(), action.float())
                # q2_loss = F.mse_loss(q2_forward.float(), y_hat.float().float())
                # q2_loss.backward()
                # soft_q2.optimizer.step()

                # Update Policy Network (ACTOR)
                action_new, action_entropy_new = policy.sample(torch.Tensor(state))
                q1_forward = soft_q1(state.float(), action_new.float())
                q2_forward = soft_q2(state.float(), action_new.float())
                q_forward = torch.min(q1_forward, q2_forward)

                policy_loss = (q_forward-(alpha * action_entropy_new)).mean()
                policy.zero_grad()
                policy_loss.backward()#torch.Tensor(sample_batch_size, 1))
                policy.optimizer.step()

                soft_q1_targets.update_params(soft_q1.state_dict(), tau)
                soft_q2_targets.update_params(soft_q2.state_dict(), tau)

                #     logging.debug(param)
                #     logging.debug(target_param)

                # for graph

                policy_loss_incr += policy_loss.item()
                q_loss_incr += q_loss.item()


            # for graph

            if _episode % 5 == 0:
                logging.info(f"EPISODE {str(_episode).ljust(4)} | reward {ep_reward:.4f} | policy-loss {policy_loss_incr:.4f}")

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
