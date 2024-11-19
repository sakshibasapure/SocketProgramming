import socket
import sys
import numpy as np
import time

# Check if enough command-line arguments are provided (at least 3 arguments)
if len(sys.argv) < 4 or len(sys.argv) > 5:
    print("Usage: python auc_client.py <server_ip> <port> <udp_port> [<packet_loss_rate>]")
    sys.exit(1)

SERVER = sys.argv[1]  # Get the server IP from command line
PORT = int(sys.argv[2])  # Get the TCP port number from command line and convert it to an integer
UDP_PORT = int(sys.argv[3])  # Get the UDP port number from command line and convert it to an integer
PACKET_LOSS_RATE = float(sys.argv[4]) if len(sys.argv) == 5 else 0.0  # Default to 0.0 if not provided

def seller_status(seller_client, msg):
    # This function checks the status of the auction request from the seller
    if msg == "Server: Invalid auction request!":
        print(msg)
        auction_request = input("Please submit auction request: ")
        seller_client.send(auction_request.encode())
        response = seller_client.recv(1024).decode()
        seller_status(seller_client, response)
    elif msg == "Server: Auction Start.":
        print("Server: Auction Start")
        return

def handle_seller(seller_client):
    print("Connected to the Auctioneer server.")
    print()
    print("Your role is: [Seller]")
    auction_request = input("Please submit auction request: ")

    seller_client.send(auction_request.encode())
    response = seller_client.recv(1024).decode()

    seller_status(seller_client, response)

    while True:
        response = seller_client.recv(1024).decode()
        if "Auction Start" in response:
            print(response)
            bidding_information = input()
            seller_client.send(bidding_information.encode())
            auctioneer_response = seller_client.recv(1024).decode()
            print(auctioneer_response)
            break

        elif "Auction finished" in response:
            # Auction has finished, print the notification message from the server
            print(response)

            winner_ip = seller_client.recv(1024).decode()  # Winning Buyer IP addr
            print(f"Winner IP address: {winner_ip}")
            

            # Step 1: Create UDP socket for data transfer to Winning Buyer
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print("UDP socket openned for RDT.")

            # Read the file to be sent
            with open("tosend.file", "rb") as file:
                file_data = file.read()

            file_length = len(file_data)
            print(f"Start sending file.")

            # Send initial control message with the total file size
            seq_num = 0  # Starting with sequence number 0
            retransmission_flag = False
            while True:
                # Send control message
                message = f"{seq_num} {file_length}".encode()
                udp_socket.sendto(message, (winner_ip, UDP_PORT))
                if retransmission_flag:
                    print(f"Msg re-sent: {seq_num}")
                else:
                    print(f"Sending control seq {seq_num}: start {file_length}")

                # Wait for ACK
                udp_socket.settimeout(2)
                try:
                    ack, _ = udp_socket.recvfrom(1024)

                    # Simulate packet loss on ACKs
                    ack_loss_flag = np.random.binomial(n=1, p=PACKET_LOSS_RATE)
                    if ack_loss_flag == 1:
                        # Discard the ACK
                        print(f"Ack dropped: {seq_num}")
                        continue  # Wait for the next ACK or timeout

                    ack_num = int(ack.decode().split()[0])
                    if ack_num == seq_num:
                        print(f"Ack received: {ack_num}")
                        break
                except socket.timeout:
                    # print(f"Timeout for control message seq {seq_num}, resending...")
                    retransmission_flag = True  # Indicate that the next send is a retransmission

            # Now proceed to data transfer
            chunk_size = 2000
            total_chunks = len(file_data) // chunk_size + (1 if len(file_data) % chunk_size else 0)
            seq_num = 1  # Starting sequence number for data transfer
            retransmission_flag = False  # Reset retransmission flag for data transfer

            for i in range(total_chunks):
                start = i * chunk_size
                end = start + chunk_size
                chunk = file_data[start:end]

                while True:
                    # Send chunk with sequence number
                    message = f"{seq_num} 1 ".encode() + chunk
                    udp_socket.sendto(message, (winner_ip, UDP_PORT))

                    if retransmission_flag:
                        print(f"Msg re-sent: {seq_num}")
                    else:
                        print(f"Sending data seq {seq_num}: {start} / {file_length}")

                    # Wait for ACK
                    udp_socket.settimeout(2)
                    try:
                        ack, _ = udp_socket.recvfrom(1024)

                        # Simulate packet loss on ACKs
                        ack_loss_flag = np.random.binomial(n=1, p=PACKET_LOSS_RATE)
                        if ack_loss_flag == 1:
                            # Discard the ACK
                            print(f"Ack dropped: {seq_num}")
                            continue  # Wait for the next ACK or timeout

                        ack_num = int(ack.decode().split()[0])
                        if ack_num == seq_num:
                            print(f"Ack received: {ack_num}")
                            # Toggle sequence number between 0 and 1 after receiving ACK
                            seq_num = 1 - seq_num
                            retransmission_flag = False  # Reset retransmission flag
                            break
                    except socket.timeout:
                        # print(f"Timeout for chunk {seq_num}, resending...")
                        retransmission_flag = True  # Indicate that the next send is a retransmission

            # End-of-transmission
            udp_socket.sendto(f"{seq_num} fin".encode(), (winner_ip, UDP_PORT))
            print(f"Sending Control Seq {seq_num}: fin")
            udp_socket.close()
            seller_client.close()
            break

        # Handle empty response when the server closes the connection
        if response == "":
            print("Server has closed the connection.")
            break

    seller_client.close()

def check_bid_status(buyer_client, msg):
    if msg == "Server: Invalid bid. Please submit a positive integer!":
        bid = input("Please submit you bid:")
        buyer_client.send(bid.encode())
        response = buyer_client.recv(1024).decode()
        check_bid_status(buyer_client, response)
    else:
        return

def handle_buyer(buyer_client):
    print("Connected to the Auctioneer server.")
    print()
    print("Your role is: [Buyer]")

    while True:
        role_message = buyer_client.recv(1024).decode()

        # Check if the server sent an empty message (connection closed)
        if not role_message:
            print("Connection closed by the server.")
            break

        print(role_message)  # Print all messages received

        if "The bidding has started!" in role_message:
            while True:  # Continue to accept bids until a valid bid is received
                bid = input("Please submit your bid: ")
                buyer_client.send(bid.encode())
                response = buyer_client.recv(1024).decode()  # Receive the server's response

                # Check if the server sent an empty message (connection closed)
                if not response:
                    print("Connection closed by the server.")
                    break

                if response == "Server: Bid received. Please wait...":
                    print(response)
                    break  # Exit the inner loop once a valid bid has been submitted
                elif response == "Server: Invalid bid. Please submit a positive integer!":
                    print("Server: Invalid bid. Please submit a positive integer!")

            # After submitting a bid, wait for the auction results
            while True:
                auction_result = buyer_client.recv(1024).decode()  # Listen for the auction result
                print(auction_result)

                # Check if the server sent an empty message (connection closed)
                if not auction_result:
                    break

                # Check for the complete auction finished message for both winners and losers
                if "You won" in auction_result:
                    seller_ip = buyer_client.recv(1024).decode()
                    buyer_ip = buyer_client.getsockname()[0]

                    print(f"Seller IP address: {seller_ip}")

                    # Step 1: Create UDP socket to receive file
                    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    udp_socket.bind((buyer_ip, UDP_PORT))

                    received_data = []
                    expected_seq = 0

                    received_size = 0  # Initialize received file size counter
                    print("UDP socket opened for RDT.")
                    print("Start receiving file.")

                    # Initialize time tracking
                    start_time = time.time()  # Record the start time of file transfer

                    while True:
                        data, addr = udp_socket.recvfrom(2048)
                        parts = data.decode(errors='ignore').split()
                        if len(parts) >= 2 and parts[1] == "fin":
                            print(f"Transmission finished.")
                            break

                        seq_num = int(parts[0])

                        # Simulate packet loss
                        flag = np.random.binomial(n=1, p=PACKET_LOSS_RATE)
                        if flag == 1:
                            # Discard the message
                            print(f"Pkt dropped: {seq_num}")
                            continue

                        if seq_num == expected_seq:
                            # Print received message sequence
                            if expected_seq == 0 and len(parts) == 2:
                                # Control message with file length
                                file_length = int(parts[1])
                                print(f"Msg received: {seq_num}")
                                print(f"Ack sent: {seq_num}")
                                udp_socket.sendto(f"{seq_num} ack".encode(), addr)
                                expected_seq = 1
                                last_ack_sent = seq_num
                                continue
                            else:
                                # Data message
                                print(f"Msg received: {seq_num}")
                                received_data.append(data[data.find(b'1 ')+2:])
                                received_size += len(data[data.find(b'1 ')+2:])  # Update received file size

                                # Print ACK sent and current received file size
                                print(f"Ack sent: {seq_num}")
                                print(f"Received data seq {seq_num}: {received_size} / {file_length}")

                                udp_socket.sendto(f"{seq_num} ack".encode(), addr)
                                last_ack_sent = seq_num
                                expected_seq = 1 - expected_seq  # Toggle expected sequence between 0 and 1
                        else:
                            # Print unexpected sequence information
                            print(f"Message received from mismatched sequence number {seq_num}. Expecting {expected_seq}")
                            if last_ack_sent is not None:
                                udp_socket.sendto(f"{last_ack_sent} ack".encode(), addr)

                    # Calculate and print time metrics after file transfer
                    end_time = time.time()  # Record the end time of file transfer
                    tct = end_time - start_time  # Total time taken (TCT) in seconds
                    at = received_size / tct  # Average throughput (AT) in bytes/second

                    # Save the received file
                    with open("recved.file", "wb") as file:
                        file.write(b"".join(received_data))

                    print("All the data received! Exiting...")
                    print(f"Transmission finished: {received_size} bytes/{tct:.2f} seconds = {at:.2f} bps")

                    udp_socket.close()
                    break  # Exit the loop after receiving the auction results

        elif "Bidding on-going" in role_message:
            print("Bidding is already in progress. You cannot join this auction.")
            buyer_client.close()
            break

    # Ensure to close the buyer_client at the end if it wasn't closed earlier
    if buyer_client:
        buyer_client.close()

if __name__ == "__main__":
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((SERVER, PORT))

    server_response = client_socket.recv(1024).decode()

    if server_response == 'seller':
        handle_seller(client_socket)
    elif server_response == 'buyer':
        handle_buyer(client_socket)
    else:
        print(server_response)
