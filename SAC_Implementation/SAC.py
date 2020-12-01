## Imports
import sys
import time

import numpy as np

import torch
import torch.nn.functional as F
from plotter import Plotter

import logging

import dmc2gym

import LogHelper
from SAC_Implementation.ReplayBuffer import ReplayBuffer
from SAC_Implementation.Networks import SoftQNetwork, PolicyNetwork


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


def one_hot(l):
    def one_hot2(i):
        """
        One-hot encoder for the states
        """
        a = np.zeros((len(i), l))
        a[range(len(i)), i] = 1
        return a

    return one_hot2


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


def initialize_nets_and_buffer(state_dim: int,
                               action_dim: int,
                               q_hidden: int,
                               policy_hidden: int,
                               learning_rates: dict,
                               replay_buffer_size: int
                               ) -> (
        SoftQNetwork, SoftQNetwork, SoftQNetwork, SoftQNetwork, PolicyNetwork, ReplayBuffer):
    """
    Method to initialize the neural networks as well as the replay buffer
    :param state_dim: Dimension of the state space
    :param action_dim: Dimension of the action space
    :param q_hidden: Hidden Size of the Q networks
    :param policy_hidden: Hidden Size of the Policy Network
    :param learning_rates: Learning Rates in an dict with keys "critic"(q-networks) and "actor"(policy)
    :param replay_buffer_size: Size of the replayBuffer
    :return: Returns the networks (Soft1, soft2, target1,target2, Policy, Buffer)
    """
    # We need to networks: 1 for the value function first
    soft_q1 = SoftQNetwork(state_dim, action_dim, q_hidden, learning_rates.get('critic'))
    soft_q2 = SoftQNetwork(state_dim, action_dim, q_hidden, learning_rates.get('critic'))

    # Then another one for calculating the targets
    soft_q1_targets = SoftQNetwork(state_dim, action_dim, q_hidden, learning_rates.get('critic'))
    soft_q2_targets = SoftQNetwork(state_dim, action_dim, q_hidden, learning_rates.get('critic'))

    policy = PolicyNetwork(state_dim, action_dim, policy_hidden, learning_rates.get('actor'))

    # Initialize the Replay Buffer
    buffer = ReplayBuffer(state_dim, action_dim,
                          replay_buffer_size)

    return soft_q1, soft_q2, soft_q1_targets, soft_q2_targets, policy, buffer


def run_sac(hyperparameter_space: dict) -> None:
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
        for _episode in range(hyperparameter_space.get('episodes')):
            # for graph
            ep_reward, policy_loss_incr, q_loss_incr, length = 0, 0, 0, 0
            logging.debug(f"Episode {_episode + 1}")

            # Observe state and action
            current_state = env.reset()
            logging.debug(f"Max Steps {hyperparameter_space.get('max_steps')}")

            for step in range(100000): # range(hyperparameter_space.get('max_steps')):
                # Do the next step
                logging.debug(f"Episode {_episode + 1} | step {step}")

                if _episode > 10:
                    action_mean, _ = sac.sample_action(torch.Tensor(current_state))
                else:
                    action_mean = env.action_space.sample()

                logging.debug(f"Our action we chose is : {action_mean}")
                logging.debug(f"The state is : {current_state}")
                logging.debug(f"Our action we chose is : {action_mean}")
                s1, r, done, _ = env.step(np.array(action_mean))

                logging.debug(f"The reward we got is {r} | {done}")
                sac.buffer.add(obs=current_state,
                               action=action_mean,
                               reward=r,
                               next_obs=s1,
                               done=done)
                ep_reward += r

                _metric = sac.update()

                policy_loss_incr += _metric[0]
                q_loss_incr += _metric[1]
                length = step

                # Update current step
                current_state = s1

                if bool(done):
                    logging.debug("Annd we are dead##################################################################")
                    break

            # for graph
            plotter.add_to_lists(reward=ep_reward,
                                 length=length,
                                 policy_loss=policy_loss_incr,
                                 q_loss=q_loss_incr)

    except KeyboardInterrupt as e:
        logging.error("KEYBOARD INTERRUPT")
    finally:
        plotter.plot()


class SACAlgorithm:
    def __init__(self, env, param: dict):
        """

        :param env:
        :param param: dict which needs following parameter:
            [hidden_dim, lr_critic, lr_policy, alpha, tau, gamma, sample_batch_size]
        """

        self.action_dim = env.action_space.shape[0]
        self.state_dim = env.observation_space.shape[0]

        logging.debug(param)

        self.soft_q1, self.soft_q2, self.soft_q1_targets, self.soft_q2_targets, self.policy, self.buffer = initialize_nets_and_buffer(
            state_dim=self.state_dim,
            action_dim=self.action_dim,
            q_hidden=param.get('hidden_dim'),
            policy_hidden=param.get('hidden_dim'),
            learning_rates={
                'critic': param.get('lr_critic'),
                'actor': param.get('lr_actor')
            },
            replay_buffer_size=param.get('replay_buffer_size'),
        )
        self.sample_batch_size, self.alpha, self.tau, self.gamma = (param.get('sample_batch_size'),
                                                                    param.get('alpha'),
                                                                    param.get('tau'),
                                                                    param.get('gamma'))

    def update(self):
        if self.buffer.length < self.sample_batch_size:
            return 0, 0

        # Sample from Replay buffer
        state, action, reward, new_state, done, _ = self.buffer.sample(batch_size=self.sample_batch_size)

        # Computation of targets
        # Here we are using 2 different Q Networks and afterwards choose the lower reward as regulator.
        y_hat_q1 = self.soft_q1_targets(state.float(), action.float())
        y_hat_q2 = self.soft_q2_targets(state.float(), action.float())
        y_hat_q = torch.min(y_hat_q1, y_hat_q2)

        # Sample the action for the new state using the policy network
        action, action_entropy = self.policy.sample(torch.Tensor(new_state))

        # We calculate the estimated reward for the next state
        y_hat = reward + self.gamma * (1 - done) * (y_hat_q - action_entropy)

        ## UPDATES OF THE CRITIC NETWORKS
        q1_forward = self.soft_q1(state.float(), action.float())
        q2_forward = self.soft_q2(state.float(), action.float())

        # Q1 Network
        q_loss = F.mse_loss(q1_forward.float(), y_hat.float()) \
                 + F.mse_loss(q2_forward.float(), y_hat.float())
        self.soft_q1.optimizer.zero_grad()
        self.soft_q2.optimizer.zero_grad()
        q_loss.backward()
        self.soft_q1.optimizer.step()
        self.soft_q2.optimizer.step()

        # Update Policy Network (ACTOR)
        action_new, action_entropy_new = self.policy.sample(torch.Tensor(state))
        q1_forward = self.soft_q1(state.float(), action_new.float())
        q2_forward = self.soft_q2(state.float(), action_new.float())
        q_forward = torch.min(q1_forward, q2_forward)

        policy_loss = (q_forward - (self.alpha * action_entropy_new)).mean()
        self.policy.zero_grad()
        policy_loss.backward()  # torch.Tensor(sample_batch_size, 1))
        self.policy.optimizer.step()

        self.soft_q1_targets.update_params(self.soft_q1.state_dict(), self.tau)
        self.soft_q2_targets.update_params(self.soft_q2.state_dict(), self.tau)

        # for graph
        return policy_loss.item(), q_loss.item()

    def sample_action(self, state: torch.Tensor):
        action, log_pi = self.policy.sample(state)
        return action.detach(), log_pi
