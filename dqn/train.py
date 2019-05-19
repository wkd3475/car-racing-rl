import torch
import gym
import torch.nn.functional as F
from torch.optim import RMSprop
from dqn.dqn import DQN
from dqn.actions import get_action_space, get_action
from dqn.replay_memory import ReplayMemory
from dqn.environment_wrapper import EnvironmentWrapper


class DQNTrainer:
    def __init__(self, params, model_path):
        self.params = params
        self.model_path = model_path
        self.current_q_net = DQN(input_shape=1, num_of_actions=get_action_space())
        self.target_q_net = DQN(input_shape=1, num_of_actions=get_action_space())
        self.optimizer = RMSprop(self.current_q_net.parameters())
        self.replay_memory = ReplayMemory(self.params.memory_capacity)
        env = gym.make('CarRacing-v0')
        self.environment = EnvironmentWrapper(env, self.params.skip_steps)

    def run(self):
        state = torch.Tensor(self.environment.reset())
        for step in range(int(self.params.num_of_steps)):
            q_value = self.current_q_net(torch.stack([state]))
            action_index, action = get_action(q_value)
            next_state, reward, done = self.environment.step(action)
            next_state = torch.Tensor(next_state)
            self.replay_memory.add(state, action_index, reward, next_state, done)
            state = next_state
            if done:
                state = torch.Tensor([self.environment.reset()])
            if len(self.replay_memory.memory) > self.params.batch_size:
                loss = self._update_current_q_net()
                print('Update: {}. Loss: {}'.format(step, loss))

    def _update_current_q_net(self):
        batch = self.replay_memory.sample(self.params.batch_size)
        states, actions, rewards, next_states, dones = batch

        states = torch.stack(states)
        next_states = torch.stack(next_states)
        actions = torch.stack(actions).view(-1, 1)
        rewards = torch.Tensor(rewards)
        dones = torch.Tensor(dones)

        q_values = self.current_q_net(states).gather(1, actions)
        next_q_values = self.target_q_net(next_states).max(1)[0]

        expected_q_values = rewards + self.params.discount_factor * next_q_values * (1 - dones)
        loss = F.smooth_l1_loss(q_values, expected_q_values.unsqueeze(1))
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        return loss